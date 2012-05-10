#!/bin/env python

import json
import bottle
from bottle import route, run, request, abort
import os
import base64
from string import Template
import time
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Job(object):
    id = None
    testsuite = None
    _current_step = 0
    _results = None

    def __init__(self, testsuite):
        self._results = []
        self.testsuite = testsuite

    def current_step(self):
        return self._current_step

    def current_testcase(self):
        return self.testsuite.flatten()[self._current_step]

    def finish_step(self, n, is_success=True, note=None):
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
        self.finish_step(self._current_step, is_success=False, note="aborted")

    def is_done(self):
        return self.completed_all_steps() or self.has_failed()

    def completed_all_steps(self):
        return len(self.testsuite.flatten()) is len(self._results)

    def has_failed(self):
        return not all(self._results) is True

    def is_running(self):
        return self._current_step < len(self.testsuite.flatten())

    def state(self):
        if "aborted" in [r["note"] for r in self._results]:
            return "ABORTED"
        if self.has_failed():
            return "FAILED"
        if self.completed_all_steps():
            return "SUCCESS"
        if self.is_running():
            return "RUNNING"
        return "FAILURE"

    def __str__(self):
        return "ID: %s\nState: %s\nStep: %d\nTestsuite:\n%s" % (self.id, 
                self.state(), self.current_step(), self.testsuite)
    def __json__(self):
        return { \
            "id": self.id,
            "testsuite": self.testsuite.__json__(),
            "state": self.state(),
            "current_step": self.current_step(),
            "_results": self._results
            }

class Testsuite(object):
    name = None
    testsets = None
    def __init__(self, ts=[]):
        self.testsets = ts
    def flatten(self):
        cases = []
        for tset in self.testsets:
            cases += tset.flatten()
        return cases
    def timeout(self):
        return sum([c.timeout for c in self.flatten()])
    def __str__(self):
        testsets_str = "\n".join([str(ts) for ts in self.testsets])
        return "Name: %s\nTestsets:\n%s" % (self.name, testsets_str)
    def __json__(self):
        return { \
            "name": self.name,
            "testsets": [t.__json__() for t in self.testsets]
            }


class Testset(object):
    testcases = None
    def __init__(self, tcases=[]):
        self.testcases = []
        self.add(tcases)
    def flatten(self):
        return self.testcases
    def timeout(self):
        return sum([c.timeout for c in self.testcases])
    def add(self, fn):
        for c in fn:
            self.testcases.append (c if isinstance(c, Testcase) else Testcase(c))
    def __str__(self):
        return str(self.flatten())
    def __json__(self):
        return {
            "testcases": [c.__json__() for c in self.testcases]
        }

class Testcase(object):
    source = None
    filename = None
    timeout = 60

    def __init__(self, filename = None):
        self.filename = filename
    def __json__(self):
        return self.__dict__


class StatemachineEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Job) or isinstance(obj, Testsuite) or \
           isinstance(obj, Testset) or isinstance(obj, Testcase):
            return obj.__json__()
        return json.JSONEncoder.default(self, obj)

if __name__ == "__main__":
    a_testsuite = Testsuite([
        Testset([ "case_a", "case_b", "case_c" ]),
        Testset([ "case_d", "case_e", Testcase(filename="case_f") ])
    ])

    print (a_testsuite)

    a_job = Job(a_testsuite)
    cur_step = 0
    while not a_job.is_done():
        print ("Working on", a_job.current_testcase())
        a_job.finish_step(cur_step, True)
        cur_step += 1
    print (a_job)
