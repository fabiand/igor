#
# Copyright (C) 2012  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Fabian Deutsch <fabiand@fedoraproject.org>
#
# -*- coding: utf-8 -*-

import logging
import threading
import time
import zlib
import pickle

import testing
import virt
import cobbler
import utils

logger = logging.getLogger(__name__)

s_open = utils.State("open")
s_preparing = utils.State("preparing")
s_prepared = utils.State("prepared")
s_running = utils.State("running")
s_aborted = utils.State("aborted")
s_failed = utils.State("failed")
s_timedout = utils.State("timedout")
s_done = utils.State("done")
endstates = [s_aborted, s_failed, s_timedout, s_done]


_high_state_change_lock = threading.Lock()
_state_change_lock = threading.Lock()

class Job(object):
    """Lifecycle
    setup()
    start()
    finish_step(..), [...] | abort()
    end()
    """
    session_path = None

    cookie = None
    session = None

    host = None

    profile = None

    testsuite = None

    current_step = 0
    results = None
    _artifacts = None

    _state = None
    _state_history = None

    _watchdog = None

    def __init__(self, cookie, testsuite, profile, host, session_path="/tmp"):
        """Create a new job to run the testsuite on host prepared with profile
        """
        self.session_path = session_path

        assert cookie is not None, "Cookie can not be None"
        self.cookie = cookie
        self.session = testing.TestSession(cookie, self.session_path)

        assert host is not None, "host can not be None"
        assert profile is not None, "profile can not be None"
        self.host = host
        self.profile = profile

        self.testsuite = testsuite

        self.results = []
        self._artifacts = []

        self._state_history = []
        self.state(s_open)

        self.watchdog = self.__init_watchdog()

    def __init_watchdog(self):
        class JobWatchdog(threading.Thread):
            job = None
            interval = 1
            _stop_event = None

            def __init__(self, job):
                self.job = job
                self._stop_event = threading.Event()
                threading.Thread.__init__(self)
                self.daemon = True

            def run(self):
                logger.debug("Starting watchdog for job %s" % self.job.cookie)
                while not self.job.is_timedout() and not self.is_stopped():
                    self._stop_event.wait(self.interval)
                with _high_state_change_lock:
                    logger.debug("Watchdog: Job %s timed out." % \
                                                               self.job.cookie)
                    self.job.state(s_timedout)
                logger.debug("Ending watchdog for job %s" % self.job.cookie)

            def stop(self):
                logger.debug("Requesting watchdog stop")
                self._stop_event.set()

            def is_stopped(self):
                return self._stop_event.is_set()

        watchdog = JobWatchdog(self)
        watchdog.start()
        return watchdog

    @utils.synchronized(_high_state_change_lock)
    def setup(self):
        """Prepare a host to get started
        """
        if self.state() != s_open:
            raise Exception(("Can not setup job %s: %s") % (self.cookie, \
                                                           self.state()))

        logger.debug("Setting up job %s" % self.cookie)
        self.state(s_preparing)
        self.host.prepare(self.session)
        self.profile.assign_to(self.host)
        self.state(s_prepared)

    @utils.synchronized(_high_state_change_lock)
    def start(self):
        """Start the actual test
        We expecte the testsuite to be gathered by the host, thus the host 
        calling in to fetch it
        """
        if self.state() != s_prepared:
            raise Exception(("Can not start job %s: %s") % (self.cookie, \
                                                            self.state()))
        logger.debug("Starting job %s" % (self.cookie))
        self.state(s_running)
        self.host.start()

    @utils.synchronized(_high_state_change_lock)
    def finish_step(self, n, is_success, note=None, is_abort=False):
        """Finish one test step
        """
        logger.debug("%s: Finishing step %s: %s (%s)" % (self.cookie, n, 
                                                             is_success, note))
        if self.state() != s_running:
            raise Exception(("Can not finish step %s of job %s, it is not" + \
                             "running anymore: %s") % (n, self.cookie, \
                                                       self.state()))

        if self.current_step != n:
            raise Exception("Expected a different step to finish.")

        current_testcase = self.testsuite.testcases()[n]
        as_expected = not is_success == current_testcase.expect_failure

        self.results.append({
            "created_at": time.time(),
            "testcase": current_testcase,
            "is_success": is_success,
            "expect_failure": current_testcase.expect_failure,
            "as_expected": as_expected,
            "is_abort": is_abort,
            "note": note
            })

        if is_abort:
            logger.debug("Aborting at step %s (%s)" % (n, \
                                                        current_testcase.name))
            self.watchdog.stop()
            self.state(s_aborted)
        elif is_success is True:
            logger.debug("Finished step %s (%s) succesfully" % (n, \
                                                        current_testcase.name))
        elif is_success is False and current_testcase.expect_failure is True:
            logger.info("Finished step %s (%s) unsucsessfull as expected" % (n, \
                                                        current_testcase.name))
        elif is_success is False:
            logger.info("Finished step %s (%s) unsucsessfull" % (n, \
                                                        current_testcase.name))
            self.watchdog.stop()
            self.state(s_failed)

        if self.completed_all_steps():
            logger.debug("Finished job %s" % (self.cookie))
            self.watchdog.stop()
            self.state(s_done)

        self.current_step += 1
        return self.current_step

    def add_artifact(self, name, data):
        aname = "%s-%s" % (self.current_step, name)
        self._artifacts.append(aname)
        self.session.add_artifact(aname, data)

    def get_artifacts_archive(self):
        return self.session.get_artifacts_archive(self._artifacts)

    def abort(self):
        """Abort the test
        """
        if self.state() != s_running:
            raise Exception(("Can not abort step %s of job %s, it is not" + \
                             "running anymore: %s") % (self.current_step, \
                                                       self.cookie, \
                                                       self.state()))

        self.finish_step(self.current_step, is_success=False, note="aborted", is_abort=True)

    @utils.synchronized(_high_state_change_lock)
    def reopen(self):
        if self.is_running(): #fixm prepare part
            raise Exception("Can not reopen job %s, it is: %s" % self.state())

        self.current_step = 0
        self.results = []
        self.state(s_running)

    @utils.synchronized(_high_state_change_lock)
    def end(self, do_cleanup=False):
        """Tear down this test, might clean up the host
        """
        logger.debug("Tearing down job %s" % self.cookie)
        if self.state() not in [s_running, s_aborted, s_failed, s_done, s_timedout]:
            raise Exception("Job %s can not yet be torn down: %s" % ( \
                                                    self.cookie, self.state()))
        self.host.purge()
        self.profile.revoke_from(self.host)
        if do_cleanup:
            self.remove()

    @utils.synchronized(_high_state_change_lock)
    def remove(self):
            self.session.remove()

    @utils.synchronized(_state_change_lock)
    def state(self, new_state=None):
        if new_state is not None:
            self._state_history.append({
                "created_at": time.time(),
                "state": new_state
            })
            self._state = new_state
        return self._state

    def result(self):
        msg = None
        if self.has_succeeded():
            msg = "success"
        elif self.has_failed():
            msg = "failed"
        elif self.is_aborted():
            msg = "aborted"
        elif self.is_timedout():
            msg = "timedout"
        elif self.is_running():
            msg = "(no result, running)"
        assert msg is not None, "Unknown job result"
        return msg

    def current_testcase(self):
        return self.testcases()[self.current_step]

    def testcases(self):
        return self.testsuite.testcases()

    def has_succeeded(self):
        m_val = self.completed_all_steps() and not self.has_failed()
        e_val = self.state() == s_done
        assert(m_val == e_val)
        return m_val

    def completed_all_steps(self):
        m_val = len(self.testcases()) == len(self.results)
        return m_val

    def has_failed(self):
        m_val = not all(self.results) is True
        e_val = self.state() == s_failed
        assert(m_val == e_val)
        return m_val

    def is_running(self):
        m_val = self.current_step < len(self.testsuite.testcases())
        e_val = self.state() == s_running
        assert(m_val == e_val)
        return m_val

    def is_aborted(self):
        m_val = "aborted" in [r["note"] for r in self.results]
        e_val = self.state() == s_aborted
        assert(m_val == e_val)
        return m_val

    def timeout(self):
        return self.testsuite.timeout()

    def runtime(self):
        runtime = 0
        now = time.time()
        get_first_state_change = lambda q: [s for s in self._state_history if s["state"] == q][0]
        if self.state() == s_running:
            time_started = get_first_state_change(s_running)["created_at"]
            runtime = now - time_started
        elif self.state() == s_timedout:
            time_started = get_first_state_change(s_running)["created_at"]
            time_ended = get_first_state_change(s_timedout)["created_at"]
            runtime = time_ended - time_started
        elif self.state() == s_aborted:
            time_started = get_first_state_change(s_running)["created_at"]
            time_ended = get_first_state_change(s_aborted)["created_at"]
            runtime = time_ended - time_started
        elif self.state() in endstates:
            time_started = get_first_state_change(s_running)["created_at"]
            time_ended = self.results[-1]["created_at"]
            runtime = time_ended - time_started
        return runtime

    def is_timedout(self):
        is_timeout = False
        if self.runtime() > self.timeout():
            is_timeout = True
        # FIXME we need to check each testcase
        return is_timeout

    def __str__(self):
        return "ID: %s\nState: %s\nStep: %d\nTestsuite:\n%s" % (self.cookie, 
                self.state(), self.current_step, self.testsuite)
    def __json__(self):
        return { \
            "id": self.cookie,
            "profile": self.profile.get_name(),
            "host": self.host.get_name(),
            "testsuite": self.testsuite.__json__(),
            "state": self.state(),
            "current_step": self.current_step,
            "results": self.results,
            "timeout": self.timeout(),
            "runtime": self.runtime()
            }


class JobCenter(object):
    """Manage jobs
    """
    session_path = None

    jobs = {}
    closed_jobs = []

    _cookie_lock = threading.Lock()

    def __init__(self, session_path):
        self.session_path = session_path
        logger.debug("JobCenter opened in %s" % self.session_path)

    def __delete__(self):
        logger.debug("JobCenter is gone.")

    def get_jobs(self):
        return {
            "all": self.jobs,
            "closed": self.closed_jobs
            }

    def _generate_cookie(self, cookie_req=None):
        cookie = cookie_req
        self._cookie_lock.acquire()
        while cookie is None or cookie in self.jobs.keys():
            cookie = "%s-%d" % (time.strftime("%Y%m%d-%H%M%S"), len(self.jobs.items()))
            cookie = utils.surl(cookie.replace("-",""))
        self._cookie_lock.release()
        assert cookie is not None, "Cookie creation failed: %s -> %s" % (cookie_req, cookie)
        return cookie

    def submit_testsuite(self, testsuite, profile, host, cookie_req=None):
        """Enqueue a testsuite to be run against a specififc build on 
        given host
        """
        cookie = self._generate_cookie(cookie_req)

        j = Job(cookie, testsuite, profile, host, session_path=self.session_path)
        j.created_at = time.time()

        self.jobs[cookie] = j

        logger.debug("Created job %s with cookie %s" % (repr(j), cookie))

        return {"cookie": cookie, "job": j}

    def start_job(self, cookie):
        job = self.jobs[cookie]
        job.setup()
        job.start()
        return "Started job %s (%s)." % (cookie, repr(job))

    def end_job(self, cookie, remove=False):
        job = self.jobs[cookie]
        job.end(remove)
        self.closed_jobs.append(job)
        return "Ended job %s." % cookie

    def abort_job(self, cookie):
        logger.debug("Aborting %s" % cookie)
        j = self.jobs[cookie]
        j.abort()
        self.closed_jobs.append(j)
        return "Aborted job %s" % cookie

    def finish_test_step(self, cookie, step, is_success,note=None):
        j = self.jobs[cookie]
        j.finish_step(step, is_success, note)
        return j

    def clean(self):
        for job in self.jobs.values():
            job.end(True)

