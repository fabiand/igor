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
import tempfile
import tarfile
import StringIO
import io
import re

import utils
from utils import run

logger = logging.getLogger(__name__)


class UpdateableObject(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Host(UpdateableObject):
    """An abstract host class to have a common set of functions
    The whole functionality relies on this functions.
    All subclasses need to implement the functions so they  can be used.

    session : TestSession
        The associated test session object.
    """
    session = None

    def prepare(self, session):
        """Prepare a host until the point where a testsuite can be submitted.
        This can involve preparing a VM or preparing a real server via some
        sophisticated stuff.
        """
        raise Exception("Not implemented.")

    def get_name(self):
        """Get a _unique_ human readbale/understandable name for this host.
        """
        raise Exception("Not implemented.")

    def get_mac_address(self):
        """The MAC address of the boot ethernet interface.
        The profile relies on PXE to be deployed, therefor we need the hosts
        mac.
        """
        raise Exception("Not implemented.")

    def purge(self):
        """Remove, erase, clean a host - if needed.
        This can be removing images of VMs or erasing a hard drive on real
        hardware.
        """
        raise Exception("Not implemented.")


class GenericHost(Host):
    """This class can be used to map to real servers
    """

    name = None
    mac = None

    def __init__(self, name, mac):
        self.name = name
        self.mac = mac

    def prepare(self, session):
        pass

    def get_name(self):
        return self.name

    def get_mac_address(self):
        return self.mac

    def purge(self):
        pass


class Profile(UpdateableObject):
    """A profile is some abstraction of an installation.
    """
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
    """A factory to build testing objects from different structures.
    The current default structure is a file/-system based approach.
    Files provide enough informations to build testsuites.
    """

    @staticmethod
    def _from_file(filename, per_line_cb):
        """Reads a file and calls a callback per line.
        This provides some functionality like ignoring comments and blank
        lines.

        per_line_cb is expected to be a callback called for each line.
        Alternatively this can also be a map of {selector: cb}, where the selector
        is determind by the pattern "^([^:]+):" on each line, e.g.:
            lib:common      # Selector: lib   >>   lib cb choosen
            tc.should       # No selector     >>   default cb choosen
        """
        fdir = os.path.dirname(filename)
        objs = []
        with open(filename, "r") as f:
            for line in f:
                line = re.sub("\s*#.*$", "", line).strip()
                if line == "":
                    continue
                cb, line = Factory._selector_based_cb_from_line(line, per_line_cb)
                obj = cb(os.path.join(fdir, line))
                if obj:
                    objs.append(obj)
        return objs

    @staticmethod
    def _selector_based_cb_from_line(line, cbmap):
        """Parse a selector from a string.
        If cbmap is a map, then the None entry is taken as the default selector

        Example:
        >>> def rcb(txt, cbm):
        ...     cb, ntxt = Factory._selector_based_cb_from_line(txt, cbm)
        ...     return cb(ntxt)
        >>> rcb("common", lambda x: x)
        'common'

        >>> cbmap = {}
        >>> cbmap[None] = lambda x: ("default", x)
        >>> cbmap["lib"] = lambda x: ("lib", x)

        >>> rcb("lib:common", cbmap)
        ('lib', 'common')

        >>> rcb("tc", cbmap)
        ('default', 'tc')
        """
        cb = None
        if callable(cbmap):
            cb = cbmap
        elif type(cbmap) is dict:
            selector_pat = re.compile("^([^:]+):")
            sel = None
            if selector_pat.match(line):
                sel = selector_pat.match(line).groups()[0]
                line = selector_pat.sub("", line)
            if sel not in cbmap:
                raise Exception("Unknown selector '%s'" % sel)
            cb = cbmap[sel]
        else:
            raise Exception("Not mapable: %s (%s)" % (cbmap, type(cbmap)))
        return (cb, line)

    @staticmethod
    def testsuites_from_path(path, suffix=".suite"):
        """Builds a dict of testsuites from *.suite files in a path.
        A filesystem layout could look like:
            suites/basic.suite
            suites/advanced.suite
            suites/minimalistic.set
            suites/example.sh           # Beeing an example testcase
        This would create a dict with two suites basic and advanced.

        >>> suites = Factory.testsuites_from_path("../testcases/")
        >>> suites["example"].libs()
        {'common': '../testcases/libs/common'}
        """
        if not os.path.exists(path):
            raise Exception("Testsuites path does not exist: %s" % path)
        suites = {}
        pat = os.path.join(path, "*%s" % suffix)
        logger.debug("Trying to load from %s" % pat)
        for f in glob.glob(pat):
            suite = Factory.testsuite_from_file(f)
            suites[suite.name] = suite
        return suites

    @staticmethod
    def testsuites_from_paths(paths, suffix=".suite"):
        """Builds a dict of testsuites from *.suite files in a list of paths.
        If more testsuites with the same name exist, the suite in the latest
        path is winning.
        Take a look at Factory.testsuites_from_path for more details.

        >>> suites = Factory.testsuites_from_paths(["../testcases/"])
        """
        suites = {}
        paths = [str.strip(p) for p in paths]
        for path in paths:
            suites.update(Factory.testsuites_from_path(path, suffix))
        return suites

    @staticmethod
    def testsuite_from_file(filename, suffix=".suite"):
        """Builds a Testsuite from a testsuite file.
        The *.suite files are expected to contain one testset file per line.
        The testset files path is relative to the testsuite file.
        Testsets can appear more than once.

        A sample testsuite could look like:
            basic.set
            selinux.set
            # Now some input
            uinput.set
            # And see if there are now denials
            selinux.set
        """
        name = os.path.basename(filename).replace(suffix, "")
        sets = Factory._from_file(filename, Factory.testset_from_file)
        return Testsuite(name=name, testsets=sets)

    @staticmethod
    def testset_from_file(filename, suffix=".set"):
        """Builds a Testset from a testset file.
        The *.set files are expected to contain one testcase file and
        optionally some arguments per line.
        The testcase files path is relative to the testset file.

        Example of a testset file:
            installation_completed.sh
            check_selinux_denials.sh
        """
        name = os.path.basename(filename).replace(suffix, "")
        testcases = []
        libs = []
        cases = Factory._from_file(filename, {
            None: Testcase.from_line,
            "lib": lambda line: libs.append(line)
        })
        return Testset(name=name, testcases=cases, libs=libs)


class Testsuite(object):
    """Represents a list of testsets.
    All testsets (and subsequently testcases) are tested in serial.
    Testsets can appear more than once.
    """

    name = None
    testsets = None

    def __init__(self, name, testsets=[]):
        self.name = name
        self.testsets = testsets

    def testcases(self):
        """All testcases of this suite.
        Removes the intermediate Testset layer. So flattens the hierarchy.
        """
        cases = []
        for tset in self.testsets:
            cases += tset.testcases()
        return cases

    def libs(self):
        """All dict of (libname, libpath) of libs
        """
        libs = {}
        for tset in self.testsets:
            libs.update(tset.libs())
        return libs

    def timeout(self):
        """Calculates the time the suite has to complete before it times out.
        This is the sum of all testcases timeouts.
        """
        return sum([int(c.timeout) for c in self.testcases()])

    def __str__(self):
        testsets_str = "\n".join([str(ts) for ts in self.testsets])
        return "Suite: %s\nTestsets:\n%s" % (self.name, testsets_str)

    def __to_dict__(self):
        """Is used to derive a JSON and XML description.
        """
        return { \
            "name": self.name,
            "testsets": [t.__to_dict__() for t in self.testsets]
            }

    def get_archive(self, subdir="testcases"):
        """Creates an archive containing all testcases and optional testcase
        connected dirs.
        Each testcase is prefixed with the step it has in the testsuite, this
        way there is a global ordering and allows testcases to appear more than
        once.
        If a testcase ism ore than just a file it can provide a folder that has
        the same name as the testcase file including a ".d" suffix.

        An example filesystem structure could look like:
        tc/examplecase.sh
        tc/complexexample.sh
        tc/complexexample.sh.d/mylib
        tc/complexexample.sh.d/mybin

        This could - depending on the testcase order - lead to the archive:
        0-complexexample.sh
        0-complexexample.sh.d/mylib
        0-complexexample.sh.d/mybin
        1-examplecase.sh

        >>> suites = Factory.testsuites_from_path("../testcases/")
        >>> suite = suites["example"]
        >>> archive = io.BytesIO(suite.get_archive().getvalue())
        >>> tarball = tarfile.open(fileobj=archive, mode="r")
        >>> tarball.getnames()
        ['testcases/0-installation_completed.sh', 'testcases/1-helloworld.sh', 'testcases/1-helloworld.sh.d', 'testcases/1-helloworld.sh.d/mylib.sh', 'testcases/2-initiate_reboot.sh', 'testcases/3-reboot_completed.sh', 'testcases/4-set_admin_password.sh', 'testcases/5-selinux-denials.py', 'testcases/lib/common', 'testcases/lib/common/common.sh']
        """
        r = io.BytesIO()
        logger.debug("Preparing archive for testsuite %s" % self.name)
        with tarfile.open(fileobj=r, mode="w:bz2") as archive:
            self.__add_testcases_to_archive(archive, subdir)
            self.__add_libs_to_archive(archive, os.path.join(subdir, "lib"))
        r.flush()
        return r

    def __add_testcases_to_archive(self, archive, subdir):
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

    def __add_testcase_to_archive(self, archive, arcname, testcase):
        srcobj = io.BytesIO(testcase.source())
        info = tarfile.TarInfo(name=arcname)
        info.size = len(srcobj.getvalue())
        info.mtime = time.time()
        archive.addfile(tarinfo=info, fileobj=srcobj)
        testcaseextradir = testcase.filename + ".d"
        if os.path.exists(testcaseextradir):
            logger.debug("Adding extra dir: %s" % testcaseextradir)
            arcname += ".d"
            archive.add(testcaseextradir, arcname=arcname, \
                        recursive=True)

    def __add_libs_to_archive(self, archive, subdir):
        for libname, libpath in self.libs().items():
            if not os.path.exists(libpath):
                logger.warning(("Adding lib '%s' / '%s' failed " + \
                                "because path does not exist.") % ( \
                                    libname, libpath))
                continue

            arcname = os.path.join(subdir, libname)
            if arcname in archive.getnames():
                logger.warning("Adding lib failed because arcname " + \
                             "with name '%s' already exists" % libname)
                continue

            logger.debug("Adding lib: %s / %s" % (libname, libpath))
            archive.add(libpath, arcname=arcname, recursive=True)


class Testset(object):
    """Represents a list of testcases.
    """

    name = None
    _libs = None
    _testcases = None

    def __init__(self, name, testcases=[], libs=None):
        self.name = name
        self._libs = {}
        self._testcases = []
        self.add(testcases)
        self.libs(libs)

    def testcases(self):
        """All testcases of this set
        """
        return self._testcases

    def libs(self, libs=None):
        """Get or set the libs (expected to be a directory) for this testset.
        libs is a list of path names, the lib name is the basename of each path

        >>> ts = Testset("foo")
        >>> ts.libs(["libs/foo"])
        {'foo': 'libs/foo'}
        >>> ts.libs({"common": "libs/special"})
        {'common': 'libs/special'}
        """
        if type(libs) is dict:
            self._libs = libs
        elif type(libs) is list:
            self._libs = {}
            for lib in libs:
                self._libs[os.path.basename(lib)] = lib
        return self._libs

    def timeout(self):
        """The timeout of this set.
        Is the sum of the timeouts of all testcases in this set.
        """
        return sum([int(c.timeout) for c in self.testcases()])

    def add(self, cs):
        """Convenience function to add a testcase by filename or as an object.
        """
        for c in cs:
            self._testcases.append(c if isinstance(c, Testcase) \
                                     else Testcase(c))

    def __str__(self):
        return "%s: %s" % (self.name, str(["%s: %s" % (n, c) for n, c in \
                                                enumerate(self.testcases())]))

    def __to_dict__(self):
        """Is used to derive a JSON and XML description.
        """
        return {
            "name": self.name,
            "testcases": [c.__to_dict__() for c in self.testcases()]
        }


class Testcase(object):
    """Represents a testcase which is mapped to a script file.
    Each testcase corresponds to a script (bash, python, ...) which is run
    on a host.
    A testcase can fail or succeed and has a timeout. Sometimes a testcase is
    expected to fail.
    """
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

    def __to_dict__(self):
        """Is used to derive a JSON and XML description.
        """
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
        with open(afilename, "wb") as afile:
            afile.write(data)

    def artifacts(self, use_abs=False):
        fns = os.listdir(self.dirname)
        if use_abs:
            fns = [os.path.join(self.dirname, fn) \
                   for fn in fns]
        return fns

    def get_artifacts_archive(self, selection=None):
        selection = selection or self.artifacts()
        r = io.BytesIO()
        logger.debug("Preparing artifacts archive for session %s" % \
                                                                   self.cookie)
        with tarfile.open(fileobj=r, mode="w:bz2") as archive:
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
