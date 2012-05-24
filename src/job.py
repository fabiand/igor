# -*- coding: utf-8 -*-

import logging
from collections import deque
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
s_done = utils.State("done")

class Job(object):
    """Lifecycle
    setup()
    start()
    finish_step(..), [...] | abort()
    end()
    """
    cookie = None
    session = None

    host = None

    profile = None

    testsuite = None
    _current_step = 0
    results = None

    state = None

    def __init__(self, cookie, testsuite, profile, host):
        """Create a new job to run the testsuite on host prepared with profile
        """
        self.cookie = cookie
        self.session = testing.TestSession(cookie)

        self.host = host
        self.profile = profile

        self.testsuite = testsuite

        self._results = []

        self.state = s_open

    def setup(self):
        """Prepare a host to get started
        """
        if self.state is not s_open:
            raise Exception(("Can not setup job %s: %s") % (self.cookie, \
                                                           self.state))

        logger.debug("Setting up job %s" % self.cookie)
        self.state = s_preparing
        self.host.prepare(self.session)
        self.profile.assign_to(self.host)
        self.state = s_prepared

    def start(self):
        """Start the actual test
        We expecte the testsuite to be gathered by the host, thus the host 
        calling in to fetch it
        """
        if self.state is not s_prepared:
            raise Exception(("Can not start job %s: %s") % (self.cookie, \
                                                            self.state))

        self.state = s_running
        self.host.start()

    def finish_step(self, n, is_success, note=None):
        """Finish one test step
        """
        logger.debug("%s: Finishing step %d w/ %s and %s" % (repr(self), n, 
                                                             is_success, note))
        if self.state is not s_running:
            raise Exception(("Can not finish step %s of job %s, it is not" + \
                             "running anymore: %s") % (n, self.cookie, \
                                                       self.state))

        if self._current_step is not n:
            raise Exception("Expected a different step to finish.")
        self._results.append({
            "is_success": is_success, 
            "note": note
            })
        self._current_step += 1
        if is_success is True:
            logger.debug("Finished step %s sucssesfully" % n)
            if self.completed_all_steps():
                logger.debug("Finished job %s" % (self.cookie))
                self.state = s_done
        elif is_success is False:
            logger.debug("Finished step %s unsucsessfull" % n)
            self.state = s_failed
        return self._current_step

    def abort(self):
        """Abort the test
        """
        if self.state is not s_running:
            raise Exception(("Can not abort step %s of job %s, it is not" + \
                             "running anymore: %s") % (n, self.cookie, \
                                                       self.state))

        self.finish_step(self._current_step, is_success=False, note="aborted")
        self.state = s_aborted

    def end(self, do_clean=False):
        """Tear down this test, might clean up the host
        """
        logger.debug("Tearing down job %s" % self.cookie)
        if self.state not in [s_aborted, s_failed, s_done]:
            raise Exception("Job %s can not yet be torn down: %s" % ( \
                                                      self.cookie, self.state))
        else:
            self.host.purge()
            self.profile.revoke_from(self.host)
            if do_cleanup:
                self.session.remove()

    def current_step(self):
        return self._current_step

    def current_testcase(self):
        return self.testcases()[self._current_step]

    def testcases(self):
        return self.testsuite.flatten()

    def is_done(self):
        m_val = self.completed_all_steps() and not self.has_failed()
        e_val = self.state is s_done
        assert(m_val is e_val)
        return m_val

    def completed_all_steps(self):
        m_val = len(self.testcases) is len(self._results)
        e_val = self.state in [s_done, s_failed, s_aborted]
        assert(m_val is e_val)
        return m_val

    def has_failed(self):
        m_val = not all(self._results) is True
        e_val = self.state is s_failed
        assert(m_val is e_val)
        return m_val

    def is_running(self):
        m_val = self._current_step < len(self.testsuite.flatten())
        e_val = self.state is s_running
        assert(m_val is e_val)
        return m_val

    def is_aborted(self):
        m_val = "aborted" in [r["note"] for r in self._results]
        e_val = self.state is s_aborted
        assert(m_val is e_val)
        return m_val

    def __str__(self):
        return "ID: %s\nState: %s\nStep: %d\nTestsuite:\n%s" % (self.cookie, 
                self.state, self.current_step(), self.testsuite)
    def __json__(self):
        return { \
            "id": self.cookie,
            "testsuite": self.testsuite.__json__(),
            "state": self.state,
            "current_step": self.current_step(),
            "_results": self._results
            }


class JobCenter(object):
    """Manage jobs
    """
    jobs = {}
    closed_jobs = []

    _cookie_lock = threading.Lock()

    def __init__(self, filename=None, autosave=False):
        pass

    def __delete__(self):
        logger.debug("JobCenter is gone.")

    def load(self, pfilename="jobcenter_data.pickle"):
        try:
            obj = None
            with open(pfilename, "r") as p:
                obj = pickle.load(p)
            self.jobs = obj["oj"]
            self.closed_jobs = obj["cj"]
        except Exception as e:
            logger.warning("Couldn't load file %s: %s" % (pfilename, \
                                                          e.message))

    def save(self, pfilename="jobcenter_data.pickle"):
        obj = {
            "oj": self.jobs,
            "cj": self.closed_jobs,
        }
        with open(pfilename, "w") as p:
            pickle.dump(obj, p)

    def get_jobs(self):
        return {
            "all": self.jobs,
            "closed": self.closed_jobs
            }

    def _generate_cookie(self, cookie_req=None):
        cookie = cookie_req
        self._cookie_lock.acquire()
        while cookie is None and cookie in self.jobs.keys():
            cookie = "%s-%d" % (time.strftime("%Y%m%d-%H%M%S"), len(self.jobs.items()))
            cookie = utils.surl(eval(cookie))
        self._cookie_lock.release()
        return cookie

    def submit_testsuite(self, testsuite, profile, host, cookie_req=None):
        """Enqueue a testsuite to be run against a specififc build on 
        given host
        """
        cookie = self._generate_cookie(cookie_req)

        j = Job(cookie, testsuite, profile, host)
        j.created_at = time.time()

        self.jobs[cookie] = j

        logger.debug("Created job %s with cookie %s" % (repr(j), cookie))

        return {"cookie": cookie, "job": j}

    def start_job(self, cookie):
        job = self.jobs[cookie]
        job.setup()
        job.start()
        return "Started job %s (%s)." % (cookie, repr(job))

    def end_job(self, cookie):
        job = self.jobs[cookie]
        job.end()
        self.closed_jobs.append(job)
        return "Ended job %s." % cookie

    def abort_job(self, cookie):
        logger.debug("Aborting %s" % cookie)
        j = self.jobs[cookie]
        j.abort()
        self.closed_jobs.append(j)
        return "Aborted job %s" % cookie

    def finish_test_step(self, cookie, step, is_success):
        j = self.jobs[cookie]
        j.finish_step(step, is_success)
        return j

    def clean(self):
        for job in self.jobs.values():
            job.end(True)

if __name__ == '__main__':
    j = JobCenter()
