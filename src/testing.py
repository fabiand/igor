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
import tempfile, tarfile
import StringIO

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


class Factory:
    @staticmethod
    def from_file(filename, per_line_cb):
        fdir = os.path.dirname(filename)
        objlist = []
        with open(filename, "r") as f:
            for setfilename in f:
                setfilename = setfilename.strip()
                objlist.append(per_line_cb(os.path.join(fdir, setfilename)))
        return objlist

    @staticmethod
    def testsuite_from_file(filename, suffix=".suite"):
        name = os.path.basename(filename).replace(suffix, "")
        sets = Factory.from_file(filename, Factory.testset_from_file)
        return Testsuite(name=name, testsets=sets)

    @staticmethod
    def testset_from_file(filename, suffix=".set"):
        name = os.path.basename(filename).replace(suffix, "")
        cases = Factory.from_file(filename, Testcase)
        return Testset(name=name, testcases=cases)

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
    def testcases(self):
        return self.flatten()
    def timeout(self):
        return sum([c.timeout for c in self.flatten()])
    def __str__(self):
        testsets_str = "\n".join([str(ts) for ts in self.testsets])
        return "Suite: %s\nTestsets:\n%s" % (self.name, testsets_str)
    def __json__(self):
        return { \
            "name": self.name,
            "testsets": [t.__json__() for t in self.testsets]
            }
    def get_archive(self, subdir="testcase.d"):
        r = StringIO.StringIO()
        with tarfile.open(fileobj=r,mode="w:bz2") as archive:
            stepn = 0
            for testcase in self.testcases():
                if testcase.filename is None:
                    logger.warning("Empty testcase: %s" % testcase.name)
                else:
                    logger.debug("Adding testcase %s" % testcase.name)
                    name = os.path.join(subdir, "%d-%s" % (stepn, os.path.basename(testcase.filename)))
                    srcobj = StringIO.StringIO(testcase.source())
                    info = tarfile.TarInfo(name=name)
                    info.size = len(srcobj.buf)
                    archive.addfile(tarinfo=info, fileobj=srcobj)
                    stepn += 1
        return r

class Testset(object):
    name = None
    testcases = None

    def __init__(self, name, testcases=[]):
        self.name = name
        self.testcases = []
        self.add(testcases)

    def flatten(self):
        return self.testcases

    def timeout(self):
        return sum([c.timeout for c in self.testcases])

    def add(self, cs):
        for c in cs:
            if not isinstance(c, Testcase):
                c = Testcase(c)
            self.testcases.append(c)

    def __str__(self):
        return "%s: %s" % (self.name, str(["%s: %s" % (n, c) for n, c in enumerate(self.flatten())]))

    def __json__(self):
        return {
            "testcases": [c.__json__() for c in self.testcases]
        }

class Testcase(object):
    name = None
    filename = None
    source = None
    timeout = 60

    def __init__(self, filename=None, name=None):
        if name is None and filename is None:
            raise Exception("At least a filename must be given")
        if name is None:
            self.name = os.path.basename(filename)
        else:
            self.name = name
        self.filename = filename
    def source(self):
        src = None
        with open(self.filename, "r") as f:
            src = f.read()
        return src
    def __str__(self):
        return "%s (%s)" % (self.name, self.filename)
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

    def remove(self):
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

    suite = Factory.testsuite_from_file("testcases/example.suite")
    print suite
    print suite.get_archive().getvalue()


    a_testsuite = Testsuite("pri", [
        Testset("one", [ "case_a", "case_b", "case_c" ]),
        Testset("two", [ "case_d", "case_e", Testcase("case_f") ])
    ])

    print (a_testsuite)

