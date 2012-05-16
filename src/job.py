# -*- coding: utf-8 -*-

import logging
from collections import deque
import threading
import time

import testing
import virt
import cobbler

logger = logging.getLogger(__name__)


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
    _results = None


    def __init__(self, cookie, testsuite, profile, host):
        """Create a new job to run the testsuite on host prepared with profile
        """
        self.cookie = cookie
        self.session = testing.TestSession(cookie)

        self.host = host
        self.profile = profile

        self.testsuite = testsuite

        self._results = []

    def setup(self):
        """Prepare a host to get started
        """
        logger.debug("Setting up job %s" % self.cookie)
        self.host.prepare(self.session)
        self.profile.assign_to(self.host)

    def start(self):
        """Start the actual test
        We expecte the testsuite to be gathered by the host, thus the host 
        calling in to fetch it
        """
        self.host.start()

    def finish_step(self, n, is_success=True, note=None):
        """Finish one test step
        """
        logger.debug("%s: Finishing step %d w/ %s and %s" % (repr(self), n, is_success, note))
        if self._current_step is not n:
            raise Exception("Expected a different step to finish.")
        self._results.append({
            "is_success": is_success, 
            "note": note
            })
        self._current_step += 1
        return self._current_step

    def abort(self):
        """Abort the test
        """
        self.finish_step(self._current_step, is_success=False, note="aborted")

    def end(self):
        """Tear down this test, might clean up the host
        """
        logger.debug("Tearing down job %s" % self.cookie)
        self.host.purge()
        self.profile.revoke_from(host)

    def current_step(self):
        return self._current_step

    def current_testcase(self):
        return self.testsuite.flatten()[self._current_step]

    def is_done(self):
        return self.completed_all_steps() or self.has_failed()

    def completed_all_steps(self):
        return len(self.testsuite.flatten()) is len(self._results)

    def has_failed(self):
        return not all(self._results) is True

    def is_running(self):
        return self._current_step < len(self.testsuite.flatten())

    def is_aborted(self):
        return "aborted" in [r["note"] for r in self._results]

    def state(self):
        if self.has_failed():
            if self.is_aborted():
                return "ABORTED"
            return "FAILED"
        if self.completed_all_steps():
            return "SUCCESS"
        if self.is_running():
            return "RUNNING"
        return "UNKNOWN"

    def __str__(self):
        return "ID: %s\nState: %s\nStep: %d\nTestsuite:\n%s" % (self.cookie, 
                self.state(), self.current_step(), self.testsuite)
    def __json__(self):
        return { \
            "id": self.cookie,
            "testsuite": self.testsuite.__json__(),
            "state": self.state(),
            "current_step": self.current_step(),
            "_results": self._results
            }


class JobCenter(object):
    """Manage jobs
    """
    open_jobs = {}
    open_jobs_queue = deque([])
    current_job = None
    closed_jobs = []

    _current_job_lock = threading.Lock()

    def __init__(self):
        pass

    def get_jobs(self):
        return {
            "open": self.open_jobs,
            "closed": self.closed_jobs
            }

    def submit_testsuite(self, testsuite, profile, host):
        """Enqueue a testsuite to be run against a specififc build on 
        given host
        """
        cookie = "%s-%d" % (time.strftime("%Y%m%d-%H%M%S"), \
                            len(self.open_jobs) + len(self.closed_jobs))

        j = Job(cookie, testsuite, profile, host)
        j.created_at = time.time()

        self.open_jobs[cookie] = j
        self.open_jobs_queue.append(j)

        logger.debug("Created job %s with cookie %s" % (repr(j), cookie))

        return {"cookie": cookie, "job": j}

    def run_next_job(self):
        msg = None
        with self._current_job_lock:
            if self.current_job is not None:
                if self.current_job.is_done():
                    self.closed_jobs.append(self.current_job)
                    msg = "Finished job %s." % repr(self.current_job)
                    self.current_job = None
                else:
                    msg = "Running job %s." % repr(self.current_job)
            else:
                msg = "No job queued."

            if self.current_job is None:
                if len(self.open_jobs) is 0:
                    msg = "No jobs."
                else:
                    self.current_job = self.open_jobs_queue.pop()
                    self.current_job.setup()
                    self.current_job.start()
                    msg = "Started job %s." % repr(self.current_job)
        return msg

    def end_current_job(self):
        msg = None
        with self._current_job_lock:
            if self.current_job is not None:
                self.current_job.end()
                self.closed_jobs.append(self.current_job)
                msg = "Ended job %s." % repr(self.current_job)
                self.current_job = None

    def abort_test(self, cookie):
        logger.debug("Aborting %s" % cookie)
        if cookie in self.open_jobs:
            j = self.open_jobs[cookie]
            j.abort()
            closed_jobs.append(j)
            del self.open_jobs[cookie]
            logger.debug("Aborted %s", repr(j))

    def finish_test_step(self, cookie, step, is_success):
        j = "Unknown job"
        if cookie in self.open_jobs:
            j = self.open_jobs[cookie]
            j.finish_step(step, is_success)
        return j

if __name__ == '__main__':
    j = JobCenter()
