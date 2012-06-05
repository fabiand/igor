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

import json
import os
import glob
import base64
from string import Template
import time
import logging
import unittest
import tempfile, tarfile
import StringIO
import re

import utils
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

    def get_name(self):
        raise Exception("Not implemented.")

    def assign_to(self, host):
        raise Exception("Not implemented.")

    def enable_pxe(self, enable):
        raise Exception("Not implemented.")

    def set_kargs(self, kargs):
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
                line = re.sub("\s*#.*$", "", line).strip()
                if line == "":
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
        cases = Factory.from_file(filename, Testcase.from_line)
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
        return sum([int(c.timeout) for c in self.testcases()])
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
        return sum([int(c.timeout) for c in self.testcases()])

    def add(self, cs):
        for c in cs:
            self._testcases.append(c if isinstance(c, Testcase) \
                                     else Testcase(c))

    def __str__(self):
        return "%s: %s" % (self.name, str(["%s: %s" % (n, c) for n, c in enumerate(self.testcases())]))

    def __json__(self):
        return {
            "name": self.name,
            "testcases": [c.__json__() for c in self.testcases()]
        }

class Testcase(object):
    name = None
    filename = None
    source = None
    timeout = 60
    expect_failure = False

    def __init__(self, filename=None, name=None):
        if name is None and filename is None:
            raise Exception("At least a filename must be given")
        if name is None:
            self.name = os.path.basename(filename)
        else:
            self.name = name
        self.filename = filename

    @staticmethod
    def from_line(line):
        token = line.split()
        token.reverse()
        assert len(token) > 0, "Testcase filename is mandatory"
        filename = token.pop()
        c = Testcase(filename)
        for k, v in utils.cmdline_to_dict(" ".join(token)).items():
            if k == "timeout":
                c.timeout = int(v)
            elif k == "expect_failure":
                c.expect_failure = utils.parse_bool(v)
        return c

    def source(self):
        src = None
        with open(self.filename, "r") as f:
            src = f.read()
        return src
    def __str__(self):
        return "%s (%s, %s)" % (self.name, self.filename, self.timeout)
    def __json__(self):
        return self.__dict__


class TestSession(UpdateableObject):
    dirname = None
    cookie = None

    do_cleanup = False

    def __init__(self, cookie, session_path, cleanup=True):
        assert session_path is not None, "session path can not be None"

        self.do_cleanup = cleanup
        self.cookie = cookie
        self.dirname = tempfile.mkdtemp(suffix="-" + self.cookie, \
                                        prefix="igord-session-", \
                                        dir=session_path)
        run("chmod a+X '%s'" % self.dirname)
        logger.info("Starting session %s in %s" % (self.cookie, self.dirname))

    def remove(self):
        logger.debug("Removing session '%s'" % self.cookie)
        for artifact in self.artifacts():
            logger.debug("Removing artifact '%s'" % artifact)
            os.remove(os.path.join(self.dirname, artifact))
        remaining_files = os.listdir(self.dirname)
        if len(remaining_files) > 0:
            logger.warning("Remaining files for session '%s': %s" % ( \
                                                            self.cookie, \
                                                            remaining_files))
        else:
            logger.debug("Removing testdir '%s'" % self.dirname)
            os.rmdir(self.dirname)

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

    def get_artifacts_archive(self, selection=None):
        selection = selection or self.artifacts()
        r = StringIO.StringIO()
        logger.debug("Preparing artifacts archive for session %s" % self.cookie)
        with tarfile.open(fileobj=r,mode="w:bz2") as archive:
            for artifact in selection:
                if artifact not in self.artifacts():
                    logger.debug("Artifact not here: %s" % artifact)
                logger.debug("Adding artifact %s" % artifact)
                archive.add(os.path.join(self.dirname, artifact), artifact)
        return r

    def __enter__(self):
        logger.debug("With session '%s'" % self.cookie)
        return self

    def __exit__(self, type, value, traceback):
        logger.debug("Ending session %s" % self.cookie)
        if self.do_cleanup:
            self.remove()
        logger.info("Session '%s' ended." % self.cookie)

if __name__ == "__main__":
    suites = Factory.testsuites_from_path("../testcases/")
    print suites
