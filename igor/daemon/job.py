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

from igor import log, utils
import main
import os
import threading
import time
import yaml


logger = log.getLogger(__name__)

s_open = utils.State("open")
s_preparing = utils.State("preparing")
s_prepared = utils.State("prepared")
s_running = utils.State("running")
s_aborted = utils.State("aborted")
s_failed = utils.State("failed")
s_timedout = utils.State("timedout")
s_passed = utils.State("passed")
endstates = [s_aborted, s_failed, s_timedout, s_passed]


_high_state_change_lock = threading.RLock()
_state_change_lock = threading.RLock()
_jobcenter_lock = threading.RLock()


class Job(object):
    """Lifecycle
    setup()
    start()
    finish_step(..), [...] | abort()
    end()
    """
    job_center = None
    session_path = None

    cookie = None
    session = None

    host = None
    profile = None
    testsuite = None
    additional_kargs = None

    current_step = 0
    results = None
    _artifacts = None

    _state = None
    _state_history = None
    state_changed = None
    _created_at = None
    _ended = False
    _ended_at = None

    _watchdog = None

    def __init__(self, job_center, cookie, jobspec, session_path="/tmp"):
        """Create a new job to run the testsuite on host prepared with profile
        """
        self.job_center = job_center
        self.session_path = session_path

        assert cookie is not None, "Cookie can not be None"
        self.cookie = cookie
        self.session = main.TestSession(cookie, self.session_path)

        testsuite, profile, host, additional_kargs = (jobspec.testsuite,
                                                      jobspec.profile,
                                                      jobspec.host,
                                                      jobspec.additional_kargs)

        assert host is not None, "host can not be None"
        assert profile is not None, "profile can not be None"
        self.host = host
        self.host.session = self.session
        self.profile = profile

        self.testsuite = testsuite

        self.additional_kargs = additional_kargs

        self.results = []
        self._artifacts = []

        self._state_history = []
        self.state_changed = threading.Event()
        self.state(s_open)

        self.watchdog = self.__init_watchdog()

        self._created_at = time.time()

    def __init_watchdog(self):
        class JobTimeoutWatchdog(utils.PollingWorkerDaemon):
            job = None

            def __init__(self, job):
                self.job = job
                utils.PollingWorkerDaemon.__init__(self)

            def work(self):
                logger.debug("Watching current step: %s" %
                             self.job.current_step)
                logger.debug("%ss of %ss (timeout) passed" % (
                             self.job.runtime(),
                             self.job.allowed_time_up_to_current_testcase()))
                if self.job.is_timedout():
                    with _high_state_change_lock:
                        logger.debug("Watchdog for job %s: timed out." %
                                     self.job.cookie)
                        self.job.state(s_timedout)
                    self.stop()

        watchdog = JobTimeoutWatchdog(self)
        return watchdog

    @utils.synchronized(_high_state_change_lock)
    def setup(self):
        """Prepare a host to get started
        """
        if self.state() != s_open:
            raise Exception(("Can not setup job %s: %s") % (self.cookie,
                                                            self.state()))

        logger.info("Setting up job %s" % self.cookie)
        self.state(s_preparing)
        logger.debug("Preparing host %s" % self.host.get_name())
        self.host.prepare()
        logger.debug("Assigning profile %s" % self.profile.get_name())
        self.additional_kargs += " %s:8080/testjob/%s" % \
                                (self.profile.remote.server_url[:-12], self.cookie)
        self.profile.assign_to(self.host, self.additional_kargs)
        self.state(s_prepared)
        self.job_center._run_hook("post-setup", self.cookie)

    @utils.synchronized(_high_state_change_lock)
    def start(self):
        """Start the actual test
        We expecte the testsuite to be gathered by the host, thus the host
        calling in to fetch it
        """
        if self.state() != s_prepared:
            raise Exception(("Can not start job %s: %s") % (self.cookie,
                                                            self.state()))
        logger.debug("Starting job %s" % (self.cookie))
        self.state(s_running)
        self.host.start()
        self.watchdog.start()
        self.job_center._run_hook("post-start", self.cookie)

    @utils.synchronized(_high_state_change_lock)
    def finish_step(self, n, is_success, note=None, is_abort=False,
                    is_skipped=False):
        """Finish one test step
        """
        logger.debug("%s: Finishing step %s: %s (%s)" % (self.cookie, n,
                                                         is_success, note))
        if self.state() != s_running:
            raise Exception(("Can not finish step %s of job %s, it is not" +
                             "running anymore: %s") % (n, self.cookie,
                                                       self.state()))

        if self.current_step != n:
            raise Exception("Expected a different step to finish.")

        last_timestamp = self.created_at
        if len(self.results) > 0:
            last_timestamp = self.results[n - 1]["created_at"]

        current_testcase = self.testsuite.testcases()[n]
        is_passed = not is_success == current_testcase.expect_failure

        log = "(log output suppressed, only for failed testcases)"
        if not is_passed:
            try:
                log = unicode(str(self.get_artifact("log")), errors='ignore')
            except:
                log = "(no log output)"

        annotations = ""
        try:
            annotations = unicode(str(self.annotations()), errors='ignore')
        except Exception as e:
            logger.debug("No annotation or error: %s" % e.message)

        self.results.append({"created_at": time.time(),
                             "testcase": current_testcase.__to_dict__(),
                             "is_success": is_success,
                             "is_passed": is_passed,
                             "is_abort": is_abort,
                             "is_skipped": is_skipped,
                             "note": note,
                             "runtime": time.time() - last_timestamp,
                             "log": log,
                             "annotations": annotations})

        if is_abort:
            logger.debug("Aborting at step %s (%s)" %
                         (n, current_testcase.name))
            self.state(s_aborted)
        elif is_skipped:
            logger.debug("Skipping step %s (%s)" %
                         (n, current_testcase.name))
        elif is_success is True:
            logger.debug("Finished step %s (%s) succesfully" %
                         (n, current_testcase.name))
        elif is_success is False and current_testcase.expect_failure is True:
            logger.info("Finished step %s (%s) unsuccessful as expected" %
                        (n, current_testcase.name))
        elif is_success is False:
            logger.info("Finished step %s (%s) unsuccessful" %
                        (n, current_testcase.name))
            self.state(s_failed)

        if len(self.testcases()) == len(self.results) and is_passed:
            self.state(s_passed)

        if self.state() in endstates:
            logger.debug("Finished job %s: %s" % (self.cookie, self.state()))
            self.watchdog.stop()
        else:
            logger.debug("Awaiting results for step %s: %s" %
                         (n + 1, self.testsuite.testcases()[n + 1]))

        self.job_center._run_hook("post-testcase", self.cookie)

        self.current_step += 1
        return self.current_step

    def annotate(self, note, step="current", is_append=True):
        """Annotate - by default - the current step.
        """
        filename = "annotations.yaml"
        if step == "current":
            filename = "%s-%s" % (self.current_step, filename)
        elif step is not None:
            filename = "%s-%s" % (step, filename)

        notes = []
        if is_append:
            try:
                data = self.get_artifact(filename)
                notes = list(yaml.load_all(data))
            except:
                logger.debug("Creating new annotation")
        notes.append(note)
        data = yaml.dump_all(notes)
        self.add_artifact(filename, data)
        self.job_center._run_hook("post-annotate", self.cookie)

    def annotations(self, step="current"):
        filename = "annotations.yaml"
        if step == "current":
            filename = "%s-%s" % (self.current_step, filename)
        elif step is not None:
            filename = "%s-%s" % (step, filename)
        return list(yaml.load_all(self.get_artifact(filename)))

    def add_artifact_to_current_step(self, name, data):
        aname = "%s-%s" % (self.current_step, name)
        self.add_artifact(aname, data)
        return aname

    def get_artifact_for_current_step(self, name):
        aname = "%s-%s" % (self.current_step, name)
        return self.get_artifact(aname)

    def add_artifact(self, name, data):
        if name not in self._artifacts:
            self._artifacts.append(name)
        self.session.add_artifact(name, data)

    def get_artifact(self, name):
        return self.session.get_artifact(name)

    def list_artifacts(self):
        return self._artifacts

    def get_artifacts_archive(self):
        logger.debug("Creating artifacts archive for: %s" % self._artifacts)
        return self.session.get_artifacts_archive(self._artifacts)

    def abort(self):
        """Abort the test
        """
        if self.state() != s_running:
            raise Exception(("Can not abort step %s of job %s, it is not" +
                             "running: %s") % (self.current_step,
                                               self.cookie,
                                               self.state()))

        self.finish_step(self.current_step, is_success=False, note="aborted",
                         is_abort=True)

    @utils.synchronized(_high_state_change_lock)
    def end(self):
        """Tear down this test, might clean up the host
        """
        logger.debug("Tearing down job %s" % self.cookie)
        if self.state() not in [s_running] + endstates:
            raise Exception("Job %s can not yet be torn down: %s" %
                            (self.cookie, self.state()))

        self.host.purge()
        self.profile.revoke_from(self.host)
        self._ended = True
        self._ended_at = time.time()
        self.job_center._run_hook("post-end", self.cookie)

    def ended_within(self, span):
        return (time.time() - self._ended_at) < span

    @utils.synchronized(_high_state_change_lock)
    def clean(self):
        assert self._ended is True
        self.session.remove()

    def time_since_end(self):
        assert self._ended is True
        return time.time() - self._ended_at

    @utils.synchronized(_state_change_lock)
    def state(self, new_state=None):
        if new_state is not None:
            self._state_history.append({
                "created_at": time.time(),
                "state": new_state
            })
            self._state = new_state
            self.state_changed.set()
            self.state_changed.clear()
        return self._state

    def result(self):
        msg = None

        if self.state() == s_passed:
            assert len(self.testcases()) == len(self.results)
            assert self.state() is not s_failed
            msg = "passed"

        elif self.state() == s_aborted:
            assert any([r["is_abort"] for r in self.results])
            msg = "aborted"

        elif self.state() == s_timedout:
            assert self.is_timedout()
            msg = "timedout"

        elif self.state() == s_failed:
            assert not all([r["is_passed"] for r in self.results])
            msg = "failed"

        elif self.state() == s_running:
            assert self.current_step < len(self.testsuite.testcases())
            msg = "(no result, running)"

        assert msg is not None, "Unknown job result"
        return msg

    def current_testcase(self):
        return self.testcases()[self.current_step]

    def testcases(self):
        return self.testsuite.testcases()

    def timeout(self):
        """The maximum time the testing part of this job can consume.
        """
        return self.testsuite.timeout()

    def runtime(self):
        """The time the job ran or is running.
        """
        runtime = 0
        now = time.time()
        get_first_state_change = lambda q: [s for s in self._state_history
                                            if s["state"] == q][0]
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
        """Check if the testsuite has timed out

        Returns:
            True if more time has passed than the sum of all testcase timeouts
        """
        is_timeout = False

        timeout = self.allowed_time_up_to_current_testcase()
        if self.runtime() > timeout:
            is_timeout = True

        return is_timeout

    def allowed_time_up_to_current_testcase(self):
        """Doesn't return the whole timeout of the whole job, but the time
        allowed until the current step
        """
        return Job._calculate_timeout_for_tcs(self.testsuite.testcases(),
                                              self.current_step)

    @staticmethod
    def _calculate_timeout_for_tcs(all_tcs, cur):
        """Calculcate the the timeout including the current testcase.

        >>> Job._calculate_timeout_for_tcs([], 0)
        0
        >>> Job._calculate_timeout_for_tcs([], 42)
        0
        >>> class Obj(object):
        ...     def __init__(self, **kwargs):
        ...         self.__dict__.update(kwargs)
        >>> tcs = [
        ...     Obj(timeout=1),
        ...     Obj(timeout=1),
        ...     ]
        >>> Job._calculate_timeout_for_tcs(tcs, 0)
        1
        >>> Job._calculate_timeout_for_tcs(tcs, 1)
        2
        >>> Job._calculate_timeout_for_tcs(tcs, 2)
        2

        Args:
            all_tcs: All testcases
            cur: The current testcase idx
        Returns:
            The timeout in seconds
        """
        # +1 because we want the timeouts, including the current one
        tcs_up_to_now = all_tcs[:cur + 1]
        return sum([t.timeout for t in tcs_up_to_now])

    def reached_endstate(self):
        """If this testsuite has reached any end state

        Returns:
            True if the testsuite reached an end
        """
        return self.state() in endstates

    def wait(self):
        """Wait for this testsuite to end
        This call blocks until this testsuite has ended.
        """
        while not self.reached_endstate():
            self.state_changed.wait()

    def __str__(self):
        return ("ID: %s\nState: %s\nStep: %d\nTestsuite:\n%s" %
                (self.cookie, self.state(), self.current_step, self.testsuite))

    def __to_dict__(self):
        return {"id": self.cookie,
                "profile": self.profile.get_name(),
                "host": self.host.get_name(),
                "testsuite": self.testsuite.__to_dict__(),
                "state": self.state(),
                "is_endstate": self.state() in endstates,
                "current_step": self.current_step,
                "results": self.results,
                "timeout": self.timeout(),
                "runtime": self.runtime(),
                "created_at": self._created_at,
                "artifacts": self._artifacts,
                "additional_kargs": self.additional_kargs}


class JobCenter(object):
    """Manage jobs
    """
    session_path = None
    hooks_path = None

    jobs = {}
    closed_jobs = []

    _queue_of_pending_jobs = []
    _queue_of_ended_jobs = []
    _pool_of_hosts_in_use = set([])

    _running_plans = {}
    _plan_results = {}

    _cookie_lock = threading.Lock()

    _worker = None

    def __init__(self, session_path, hooks_path=None):
        self.session_path = session_path
        self.hooks_path = hooks_path
        if not os.path.exists(self.session_path):
            os.makedirs(self.session_path)

        logger.debug("JobCenter opened in %s" % self.session_path)

        self._worker = JobCenter.JobWorker(jc=self, cleanup_age=5 * 60)
        self._worker.start()

    def __del__(self):
        self._worker.stop()
        logger.debug("JobCenter is gone.")

    @utils.synchronized(_jobcenter_lock)
    def get_jobs(self):
        return {"all": self.jobs,
                "closed": self.closed_jobs}

    def _generate_cookie(self, cookie_req=None):
        cookie = cookie_req
        self._cookie_lock.acquire()
        while cookie is None or cookie in self.jobs.keys():
            cookie = "%s-%d" % (time.strftime("%Y%m%d-%H%M%S"),
                                len(self.jobs.items()))
            cookie = "i" + utils.surl(cookie.replace("-", ""))
        self._cookie_lock.release()
        assert cookie is not None, ("Cookie creation failed: %s -> %s" %
                                    (cookie_req, cookie))
        return cookie

    @utils.synchronized(_jobcenter_lock)
    def submit(self, jobspec, cookie_req=None):
        """Enqueue a jobspec to be run against a specififc build on
        given host
        """
        cookie = self._generate_cookie(cookie_req)

        j = Job(self, cookie, jobspec, session_path=self.session_path)
        j.created_at = time.time()

        self.jobs[cookie] = j

        logger.debug("Created job %s with cookie %s" % (repr(j), cookie))

        logger.info("Job %s got submitted." % cookie)

        return {"cookie": cookie, "job": j}

    @utils.synchronized(_jobcenter_lock)
    def start_job(self, cookie):
        self._queue_of_pending_jobs.append(cookie)
        return "Started job %s. %d in queue" % \
            (cookie, len(self._queue_of_pending_jobs))

    def _start_job(self, cookie):
        job = self.jobs[cookie]
        if job.host in self._pool_of_hosts_in_use:
            raise Exception("The host is already in use: %s" % job.cookie)
        self._pool_of_hosts_in_use.add(job.host)

        logger.info("Job %s is beeing started." % cookie)
        job.setup()
        job.start()
        logger.info("Job %s got started." % cookie)

        return "Started job %s (%s)." % (cookie, repr(job))

    @utils.synchronized(_jobcenter_lock)
    def finish_test_step(self, cookie, step, is_success, note=None):
        j = self.jobs[cookie]
        j.finish_step(step, is_success, note)
        logger.info("Job %s finished step %s" % (cookie, step))
        return j

    @utils.synchronized(_jobcenter_lock)
    def skip_step(self, cookie, step, note=None):
        j = self.jobs[cookie]
        j.finish_step(step, False, note, is_skipped=True)
        logger.info("Job %s skipped step %s" % (cookie, step))
        return j

    @utils.synchronized(_jobcenter_lock)
    def test_step_result(self, cookie, step):
        j = self.jobs[cookie]
        return j.results[step]

    @utils.synchronized(_jobcenter_lock)
    def abort_job(self, cookie):
        logger.debug("Aborting %s" % cookie)
        j = self.jobs[cookie]
        j.abort()
        logger.info("Job %s aborted." % (cookie))
        return j

    def _end_job(self, cookie):
        job = self.jobs[cookie]
        job.end()
        if job.host not in self._pool_of_hosts_in_use:
            logger.warning("The host was not in use: %s" % job.cookie)
        self._pool_of_hosts_in_use.discard(job.host)
        self.closed_jobs.append(job)
        #del self.jobs[job]
        # cant poll the status if we remove the job from jobs
        logger.info("Job %s ended." % cookie)
        return "Ended job %s." % cookie

    def submit_plan(self, plan):
        if plan.name in self._running_plans:
            raise Exception("Plan with same name already running: %s" %
                            plan.name)
        running_plan = JobCenter.PlanWorker(self, plan)
        running_plan.start()
        self._running_plans[plan.name] = running_plan
        return running_plan

    def status_plan(self, name):
        results = None
        if name in self._running_plans:
            results = self._running_plans[name].__to_dict__()
        elif name in self._plan_results:
            results = self._plan_results[name]
        return results

    def abort_plan(self, name):
        if name not in self._running_plans:
            #raise Exception("Plan is not running: %s" % name)
            return None
        return self._running_plans[name].stop()

    def _run_hook(self, hook, cookie):
        allowed_hooks = ["pre-job", "post-job", "post-testcase",
                         "post-setup", "post-start", "post-annotate",
                         "post-end"]
        cmd_tpl = "{script} {hook} {cookie}"
        if hook in allowed_hooks and os.path.isdir(self.hooks_path):
            for scriptfile in os.listdir(self.hooks_path):
                script = os.path.join(self.hooks_path, scriptfile)
                cmd = cmd_tpl.format(script=script, hook=hook,
                                     cookie=cookie)
                logger.debug("Running hook: %s" % cmd)
                os.system(cmd)
        elif hook not in allowed_hooks:
            logger.warning("Unknown hook: %s" % hook)

    class PlanWorker(threading.Thread):
        jc = None
        plan = None

        created_at = 0

        passed = False
        current_job = None
        jobs = None

        status = None

        _do_end = False

        def __init__(self, jc, plan):
            threading.Thread.__init__(self)
            self.daemon = True

            self.jc = jc
            self.plan = plan
            self.created_at = time.time()
            self.jobs = []

        def run(self):
            logger.debug("Starting plan %s" % self.plan.name)
            self.status = "running"

            for jobspec in self.plan.job_specs():
                resp = self.jc.submit(jobspec)
                cookie, self.current_job = (resp["cookie"], resp["job"])
                self.jc.start_job(cookie)
                self.jobs.append(self.current_job)
                self.current_job.wait()

                if self._do_end:
                    logger.debug("Plan stopped: %s" % self.plan.name)
                    self.passed = False
                    break

            self.passed = all([r.state() == s_passed
                               for r in self.jobs])
#            self.jobs.reverse()
            self.status = "stopped"

            self.jc._plan_results[self.plan.name] = self.__to_dict__()
            del self.jc._running_plans[self.plan.name]
            logger.debug("Plan ended: %s" % self.plan.name)

        def stop(self):
            logger.debug("Request to stop plan %s" % self.plan.name)
            self._do_end = True
            if self.current_job:
                self.jc.abort_job(self.current_job.cookie)
            return self

        def runtime(self):
            return time.time() - self.created_at

        def __to_dict__(self):
            return {
                "plan": self.plan.__to_dict__(),
                "jobs": [r.__to_dict__() for r in self.jobs],
                "current_job_cookie": self.current_job.cookie
                if self.current_job else "",
                "passed": self.passed,
                "runtime": self.runtime(),
                "created_at": self.created_at,
                "status": self.status
            }

    class JobWorker(utils.PollingWorkerDaemon):
        jc = None
        cleanup_age = None
        max_cleaned_jobs = 10

        def __init__(self, jc, cleanup_age):
            self.jc = jc
            self.cleanup_age = cleanup_age
            utils.PollingWorkerDaemon.__init__(self)

        def work(self):
            if len(self.jc._queue_of_pending_jobs) == 0:
                # No item
                pass
            else:
                # FIXME this doesn't respect the order
                for cookie in self.jc._queue_of_pending_jobs:
                    candidate = self.jc.jobs[cookie]
                    logger.debug("Checking if host is in use: %s" %
                                 candidate.host)
                    if candidate.host in self.jc._pool_of_hosts_in_use:
                        self._debug("Host of candidate %s is still in use" %
                                    cookie)
                    else:
                        self._debug("Starting job %s" % cookie)
                        self.jc._run_hook("pre-job", cookie)
                        self.jc._start_job(cookie)
                        self.jc._queue_of_pending_jobs.remove(cookie)

            # Look for ended jobs
            for cookie, j in self.jc.jobs.items():
                if j.reached_endstate():
                    if not j._ended:
                        self._debug("Unwinding job %s" % cookie)
                        self.jc._run_hook("post-job", cookie)
                        self.jc._end_job(j.cookie)
                        self.jc._queue_of_ended_jobs.append(j)

            while len(self.jc._queue_of_ended_jobs) > self.max_cleaned_jobs:
                self._remove_oldest_job()

        def _remove_oldest_job(self):
            oldest_job = None

            for job in self.jc._queue_of_ended_jobs:
                if oldest_job is None \
                   or job.created_at < oldest_job.created_at \
                   and not oldest_job.ended_within(self.cleanup_age):
                    oldest_job = job

            if oldest_job is not None:
                self._debug("Cleaning job %s" % oldest_job.cookie)
                oldest_job.clean()
                self.jc._queue_of_ended_jobs.remove(oldest_job)
                del self.jc.jobs[oldest_job.cookie]
                logger.info("Job %s cleaned and removed." % oldest_job.cookie)
