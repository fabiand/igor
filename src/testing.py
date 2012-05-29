# -*- coding: utf-8 -*-

import json
import bottle
from bottle import route, run, request, abort
import os
import glob
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
            for line in f:
                line = line.strip()
                if line.startswith("#") or line == "":
                    continue
                objlist.append(per_line_cb(os.path.join(fdir, line)))
        return objlist

    @staticmethod
    def testsuites_from_path(path, suffix=".suite"):
        suites = {}
        pat = os.path.join(path, "*%s" % suffix)
        logger.debug("Trying to load from %s" % pat)
        for f in glob.glob(pat):
            suite = Factory.testsuite_from_file(f)
            suites[suite.name] = suite
        return suites

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

    def testcases(self):
        cases = []
        for tset in self.testsets:
            cases += tset.testcases()
        return cases

    def timeout(self):
        return sum([c.timeout for c in self.testcases()])
    def __str__(self):
        testsets_str = "\n".join([str(ts) for ts in self.testsets])
        return "Suite: %s\nTestsets:\n%s" % (self.name, testsets_str)
    def __json__(self):
        return { \
            "name": self.name,
            "testsets": [t.__json__() for t in self.testsets]
            }
    def get_archive(self, subdir="testcases"):
        r = StringIO.StringIO()
        logger.debug("Preparing archive for testsuite %s" % self.name)
        with tarfile.open(fileobj=r,mode="w:bz2") as archive:
            stepn = 0
            for testcase in self.testcases():
                logger.debug("Adding testcase #%s: %s" % (stepn, \
                                                          testcase.name))
                if testcase.filename is None:
                    logger.warning("Empty testcase: %s" % testcase.name)
                    continue

                arcname = os.path.join(subdir, "%d-%s" % (stepn, \
                                          os.path.basename(testcase.filename)))
                self.__add_testcase_to_archive(archive, arcname, testcase)
                stepn += 1
        return r

    def __add_testcase_to_archive(self, archive, arcname, testcase):
        srcobj = StringIO.StringIO(testcase.source())
        info = tarfile.TarInfo(name=arcname)
        info.size = len(srcobj.buf)
        archive.addfile(tarinfo=info, fileobj=srcobj)
        testcaseextradir = testcase.filename + ".d"
        if os.path.exists(testcaseextradir):
            logger.debug("Adding extra dir: %s" % testcaseextradir)
            archive.add(testcaseextradir, arcname=arcname + ".d", \
                        recursive=True)

class Testset(object):
    name = None
    _testcases = None

    def __init__(self, name, testcases=[]):
        self.name = name
        self._testcases = []
        self.add(testcases)

    def testcases(self):
        return self._testcases

    def timeout(self):
        return sum([c.timeout for c in self.testcases()])

    def add(self, cs):
        for c in cs:
            if not isinstance(c, Testcase):
                c = Testcase(c)
            self._testcases.append(c)

    def __str__(self):
        return "%s: %s" % (self.name, str(["%s: %s" % (n, c) for n, c in enumerate(self.testcases())]))

    def __json__(self):
        return {
            "testcases": [c.__json__() for c in self.testcases()]
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

    def add_artifact(self, name, data):
        assert("/" not in name and "\\" not in name)
        afilename = os.path.join(self.dirname, name)
        # fixme collsisions
        with open(afilename, "w") as afile:
            afile.write(data)

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
    #print suite.get_archive().getvalue()
    suites = Factory.testsuites_from_path("testcases")
    print suites["example"] == suite


    a_testsuite = Testsuite("pri", [
        Testset("one", [ "case_a", "case_b", "case_c" ]),
        Testset("two", [ "case_d", "case_e", Testcase("case_f") ])
    ])

    print (a_testsuite)

