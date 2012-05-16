# -*- coding: utf-8 -*-

import json
import bottle
from bottle import route, run, request, abort
import os
import base64
from string import Template
import time
import logging
import unittest

from utils import run

logger = logging.getLogger(__name__)


available_hosts = set()
available_profiles = set()
avialable_testcases = set()


class UpdateableObject(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Host(UpdateableObject):
    session = None

    def prepare(self, session):
        raise Exception("Not implemented.")

    def submit_testsuite(self, testsuite):
        raise Exception("Not implemented.")

    def get_name(self):
        raise Exception("Not implemented.")

    def get_mac_address(self):
        raise Exception("Not implemented.")

    def purge(self):
        raise Exception("Not implemented.")


class Profile(UpdateableObject):
    def assign_to(self, host):
        raise Exception("Not implemented.")

    def revoke_from(self, host):
        raise Exception("Not implemented.")



class Testsuite(object):
    name = None
    testsets = None
    def __init__(self, name, testsets=[]):
        self.name = name
        self.testsets = testsets
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
    name = None
    testcases = None

    def __init__(self, name, testcases):
        self.testcases = []
        self.add(testcases)

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
    name = None
    source = None
    filename = None
    timeout = 60

    def __init__(self, name, filename = None, source=None):
        self.filename = filename
        self.source = source
    def __json__(self):
        return self.__dict__


class TestSession(UpdateableObject):
    dirname = None
    cookie = None

    do_cleanup = False

    def __init__(self, cookie, cleanup=True):
        self.do_cleanup = cleanup
        self.cookie = cookie
        self.dirname = run("mktemp -d '/tmp/test-session-%s-XXXX'" % \
                           self.cookie)
        run("chmod a+X '%s'" % self.dirname)
        logger.info("Starting session %s in %s" % (self.cookie, self.dirname))

    def close(self):
        logger.debug("Removing testdir '%s'" % self.dirname)
        for artifact in self.artifacts():
            logger.debug("Removing artifact '%s'" % artifact)
            os.remove(os.path.join(self.dirname, artifact))
        os.removedirs(self.dirname)

    def artifacts(self, use_abs = False):
        fns = os.listdir(self.dirname)
        if use_abs:
            fns = [os.path.join(self.dirname, fn) \
                   for fn in fns]
        return fns

    def __enter__(self):
        logger.debug("With session '%s'" % self.cookie)
        return self

    def __exit__(self, type, value, traceback):
        logger.debug("Ending session %s" % self.cookie)
        if self.do_cleanup:
            self.remove()
        logger.info("Session '%s' ended." % self.cookie)

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
