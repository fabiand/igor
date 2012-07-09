# -*- coding: utf-8 -*-
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
import shlex
from threading import Lock

import utils
from utils import run

logger = logging.getLogger(__name__)


class UpdateableObject(object):
    def __init__(self, **kwargs):
        self.update_props(kwargs)

    def update_props(self, kwargs):
        self.__dict__.update(kwargs)


class Host(UpdateableObject):
    """An abstract host class to have a common set of functions
    The whole functionality relies on this functions.
    All subclasses need to implement the functions so they  can be used.

    session : TestSession
        The associated test session object - set when associated with a Job
    origin : testing.Origin
        The corresponding origin - associated by Origin
    """
    session = None
    origin = None

    def prepare(self):
        """Prepare a host until the point where a testsuite can be submitted.
        This can involve preparing a VM or preparing a real server via some
        sophisticated stuff.
        """
        raise Exception("Not implemented.")

    def start(self):
        """Boot the host
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

    def __to_dict__(self):
        return {
                "name": self.get_name(),
                "origin": self.origin
            }


class GenericHost(Host):
    """This class can be used to map to real servers
    """

    name = None
    mac = None

    def prepare(self):
        pass

    def get_name(self):
        return self.name

    def get_mac_address(self):
        return self.mac


class Profile(UpdateableObject):
    """A profile is some abstraction of an installation.
    """

    origin = None

    def get_name(self):
        """Get the unique name of this profile
        """
        raise Exception("Not implemented.")

    def assign_to(self, host):
        raise Exception("Not implemented.")

    def enable_pxe(self, enable):
        raise Exception("Not implemented.")

    def kargs(self, kargs):
        raise Exception("Not implemented.")

    def revoke_from(self, host):
        raise Exception("Not implemented.")

    def delete(self):
        raise Exception("Not implemented.")

    def __to_dict__(self):
        return {
                "name": self.get_name(),
                "origin": self.origin
            }


class Origin(object):
    def name(self):
        raise Exception("Not implemented.")

    def items(self):
        """Returns a dict name:item-obj
        """
        raise Exception("Not implemented.")

    def lookup(self, name):
        """Returns an item-obj
        """
        item = None
        items = self.items()
        if name in items:
            item = items[name]
        return item

    def create_item(self, **kwargs):
        """Create an item at origin (or default origin if None)
        """
        raise Exception("Not implemented.")

    def __to_dict__(self):
        return {
                "name": self.name(),
            }


class Inventory(object):
    """Is a central repository for Igor related items.
    This inventory can be used to lookup *existsing* items.
    Use a factory to create the objects, or pass a Factory as a callback.
    """

    _origins = None

    def __init__(self, plans={}, testsuites={}, profiles={}, hosts={}):
        """Each parameter is a list of callbacks to list all items of that
        category.

        The callbacks are expected to have the form
            cb() => dict
        The callback returns a dict mapping a unique identifier to an object
        of the category (Host, Profile, Testsuite) in question.

        A basic example:
        >>> f = Origin()
        >>> f.items = lambda: {"item-a": "a", "item-b": "b"}
        >>> s = Origin()
        >>> s.items = lambda: {"item-c": "c", "item-d": "d"}
        >>> i = Inventory(plans={"a": f, \
                                 "b": s})
        >>> i.plans()
        {'item-a': 'a', 'item-b': 'b', 'item-c': 'c', 'item-d': 'd'}

        Or even use a factory to populate the inventory:
        >>> f = FilesystemTestsuitesOrigin(["../testcases/suites/"])
        >>> i = Inventory(testsuites={"fs": f})
        >>> "examplesuite" in i.testsuites()
        True
        """
        self._origins = {
            "plans": {},
            "testsuites": {},
            "profiles": {},
            "hosts": {}
        }
        for (k, origins) in [("plans", plans), ("testsuites", testsuites), \
                         ("profiles", profiles), ("hosts", hosts)]:
            self._add_origins(k, origins)

    def _add_origins(self, k, origins):
        assert type(origins) is dict
        for name, origin in origins.items():
            if not isinstance(origin, Origin):
                raise Exception(("Invalid %s origin '%s': '%s'") % (k, \
                                                               source, origin))
            self._origins[k][name] = origin

    def _items(self, k):
        """Retrieves all items from all origins
        """
        all_items = {}
        for name, origin in self._origins[k].items():
            items = origin.items()
            for item in items:
                if item in all_items:
                    raise Exception(("Item name is not unique over all %s " + \
                                     "origins: %s") % (k, item))
            if type(items) is not dict:
                raise Exception("%s did not return a dict." % k)
            all_items.update(items)
        return all_items

    def _lookup(self, k, q=None):
        if q is None:
            return self._items(k)
        item = None
        for name, origin in self._origins[k].items():
            item = origin.lookup(q)
            if item is not None:
                break
        return item

    def plans(self, q=None):
        return self._lookup("plans", q)

    def testsuites(self, q=None):
        return self._lookup("testsuites", q)

    def profiles(self, q=None):
        return self._lookup("profiles", q)

    def hosts(self, q=None):
        return self._lookup("hosts", q)

    def check(self):
        logger.debug("Self checking invetory …")
        ps = self.plans()
        ts = self.testsuites()
        prs = self.profiles()
        hs = self.hosts()
        n = 10
        logger.debug("Found %d plan(s): %s …" % (len(ps), ps.keys()[0:n]))
        logger.debug("Found %d testsuite(s): %s …" % (len(ts), \
                                                      ts.keys()[0:n]))
        logger.debug("Found %d profiles(s): %s …" % (len(prs), \
                                                     prs.keys()[0:n]))
        logger.debug("Found %d hosts(s): %s …" % (len(hs), \
                                                      hs.keys()[0:n]))

    def create_profile(self, oname, pname, kernel, initrd, kargs):
        """Create a profile in the profile origin with the name.
        """
        if oname not in self._origins["profiles"]:
            raise Exception("Unknown origin: %s" % oname)
        origin = self._origins["profiles"][oname]
        origin.create_item(pname, kernel, initrd, kargs)


class FilesystemTestsuitesOrigin(Origin):
    paths = None

    def __init__(self, paths):
        if type(paths) is not list:
            paths = [paths]
        self.paths = paths

    def name(self):
        return "FilesystemTestsuitesOrigin(%s)" % self.paths

    def items(self):
        testsuites = Factory.testsuites_from_paths(self.paths)
        return testsuites


class FilesystemTestplansOrigin(Origin):
    paths = None

    def __init__(self, paths):
        if type(paths) is not list:
            paths = [paths]
        self.paths = paths

    def name(self):
        return "FilesystemPlansOrigin(%s)" % self.paths

    def items(self):
        plans = Factory.testplans_from_paths(self.paths)
        return plans


class Factory(utils.Factory):
    """A factory to build testing objects from different structures.
    The current default structure is a file/-system based approach.
    Files provide enough informations to build testsuites.
    """

    @staticmethod
    def testplan_from_file(filename, suffix=".plan"):
        """Builds a Testplan from a testplan file.
        The *.plan files are expected to contain one (testsuite, profile, host)
        tuple per line.

        A sample tesplan could look like:
            # Some comment:
            basic minimal_pkg_set highend_server kargs="tuiinstall"
            basic maximal_pkg_set highend_server kargs="firstboot trigger=url"
        """
        name = os.path.basename(filename).replace(suffix, "")
        layouts = Factory._from_file(filename, {
                    None: lambda line: Factory._line_to_job_layout(line)
                })
        return Testplan(name=name, job_layouts=layouts)

    @staticmethod
    def _line_to_job_layout(line):
        """Expects a line with at least three tokens: (testsuite, profile, 
        host), [kargs='...']

        >>> Factory._line_to_job_layout("s p h")
        {'profile': 'p', 'testsuite': 's', 'host': 'h', 'kargs': None}

        >>> Factory._line_to_job_layout("s p h kargs='foo'")
        {'profile': 'p', 'testsuite': 's', 'host': 'h', 'kargs': 'foo'}
        """
        tokens = shlex.split(line)
        if len(tokens) < 3:
            raise Exception("Not enough params in plan line: '%s'" % line)
        t, p, h = tokens[0:3]
        layout = {
            "testsuite": t,
            "profile": p,
            "host": h,
            "kargs": None
            }
        if len(tokens) == 4:
            if tokens[3].startswith("kargs="):
                layout["kargs"] = tokens[3].replace("kargs=", "")
        return layout

    @staticmethod
    def testplans_from_paths(paths, suffix=".plan"):
        """Builds a dict of testplans from *.plans files in a path.
        A filesystem layout could look like:
            suites/basic.plan
            suites/advanced.plan
        This would create a dict with two plans basic and advanced.

        >>> plans = Factory.testplans_from_path("../data/")
        >>> "exampleplan" in plans
        True

        >>> plans["exampleplan"].name = "exampleplan"
        """
        assert type(paths) is list
        plans = {}
        for path in paths:
            if not os.path.exists(path):
                raise Exception("Testplan path does not exist: %s" % path)
            pat = os.path.join(path, "*%s" % suffix)
            logger.debug("Loading plan from %s" % pat)
            for f in glob.glob(pat):
                plan = Factory.testplan_from_file(f)
                assert plan.name not in plans, "Only unique plan names allowed"
                plans[plan.name] = plan
        return plans

    @staticmethod
    def testsuites_from_path(path, suffix=".suite"):
        """Builds a dict of testsuites from *.suite files in a path.
        A filesystem layout could look like:
            suites/basic.suite
            suites/advanced.suite
            suites/minimalistic.set
            suites/example.sh           # Beeing an example testcase
        This would create a dict with two suites basic and advanced.

        >>> suites = Factory.testsuites_from_path("../testcases/suites/")
        >>> suites["examplesuite"].libs()
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

        >>> suites = Factory.testsuites_from_paths(["../testcases/suites/"])
        >>> "examplesuite" in suites
        True
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
        v = {"searchpath": "."}
        rp = lambda line: os.path.relpath(os.path.realpath(os.path.join( \
                            os.path.dirname(filename), \
                            v["searchpath"], \
                            line)))
        sets = Factory._from_file(filename, {
            None: lambda line: Factory.testset_from_file(rp(line)),
            "searchpath": lambda line: v.update({"searchpath": line})
        })
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
        v = {"searchpath": "."}
        rp = lambda line: os.path.relpath(os.path.realpath(os.path.join( \
                            os.path.dirname(filename), \
                            v["searchpath"], \
                            line)))
        testcases = []
        libs = []
        cases = Factory._from_file(filename, {
            None: lambda line: Testcase.from_line(rp(line)),
            "lib": lambda line: libs.append(rp(line)),
            "searchpath": lambda line: v.update({"searchpath": line})
        })
        return Testset(name=name, testcases=cases, libs=libs)


class JobSpec(UpdateableObject):
    """Specifies a job, consiting of testsuite, profile and host
    """
    testsuite = None
    host = None
    profile = None
    kargs = None

    def __to_dict__(self):
        return self.__dict__

    def __str__(self):
        return str(self.__to_dict__())


class Testplan(object):
    """Runs a list of testsuites on profile/host.

    Attributes
    ----------
    job_specs : List of tuples
        A list of (testsuite, profile, host, kargs) tuples to be run.
    """
    name = None
    job_layouts = None
    inventory = None

    def __init__(self, name, job_layouts, inventory=None):
        self.name = name
        self.job_layouts = job_layouts
        self.inventory = None

    def timeout(self):
        return sum([t.timeout() for t in self.job_specs().testsuite])

    def job_specs(self):
        specs = []
        inventory = self.inventory
        for layout in self.job_layouts:
            spec = JobSpec(
                testsuite=inventory.testsuites()[layout["testsuite"]],
                profile=inventory.profiles()[layout["profile"]],
                host=inventory.hosts()[layout["host"]]
            )
            specs.append(spec)
        return specs

    def __str__(self):
        return str(self.__to_dict__())

    def __to_dict__(self):
        return {
                "name": self.name,
                "job_layouts": self.job_layouts
                }

    def __hash__(self):
        return hash(str(self.name))


class Testsuite(object):
    """Represents a list of testsets.
    All testsets (and subsequently testcases) are tested in serial.
    Testsets can appear more than once.
    """

    name = None
    testsets = None
    origin = None

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

        >>> suites = Factory.testsuites_from_path("../testcases/suites/")
        >>> suite = suites["examplesuite"]
        >>> archive = io.BytesIO(suite.get_archive().getvalue())
        >>> tarball = tarfile.open(fileobj=archive, mode="r")
        >>> import re
        >>> all([re.match("testcases/", n) for n in tarball.getnames()])
        True
        >>> any([re.match("testcases/lib/", n) for n in tarball.getnames()])
        True
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

            logger.debug("Adding library '%s' from '%s'" % (libname, libpath))
            archive.add(libpath, arcname=arcname, recursive=True)

    def validate(self):
        """Validate that all paths and check testcases can be gathered
        """
        valid = True
        try:
            self.get_archive()
        except:
            valid = False
        return valid


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
    description = None

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
