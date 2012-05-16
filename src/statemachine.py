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


def to_json(obj):
    return json.dumps(obj, cls=StatemachineEncoder, sort_keys=True, indent=2)

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
