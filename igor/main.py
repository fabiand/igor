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

"""
The main module of igor, specifying the model.
"""

import os
import time
import logging
import tempfile
import tarfile
import io
import random

from igor.utils import run, update_properties_only

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
    origin : Origin
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
        """Get a _unique_ name for this host.
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


class Profile(UpdateableObject):
    """A profile is some abstraction of an installation.
    """

    origin = None

    def get_name(self):
        """Get the unique name of this profile
        """
        raise Exception("Not implemented.")

    def assign_to(self, host, additional_kargs=""):
        raise Exception("Not implemented.")

    def enable_pxe(self, enable):
        raise Exception("Not implemented.")

    def kargs(self, kargs):
        raise Exception("Not implemented.")

    def revoke_from(self, host):
        raise Exception("Not implemented.")

    def delete(self):
        raise Exception("Not implemented.")

    def __repr__(self):
        return "<%s name='%s'>" % (self.__class__.__name__, self.get_name())

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
        >>> import igor.backends.files
        >>> f = igor.backends.files.TestsuitesOrigin(["testcases/suites/"])
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
#            if isinstance(origin, Origin):
#                raise Exception(("Invalid %s origin '%s': '%s'") % (k, \
#                                                               name, origin))
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
        logger.debug("Looking up %s: %s" % (k, q))
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


class JobSpec(UpdateableObject):
    """Specifies a job, consiting of testsuite, profile and host
    """
    testsuite = None
    host = None
    profile = None
    additional_kargs = None

    def __to_dict__(self):
        return self.__dict__

    def __str__(self):
        return str(self.__to_dict__())


class Testplan(object):
    """Runs a list of testsuites on profile/host.

    Attributes
    ----------
    job_layouts : List of tuples
        A list of (testsuite, profile, host, kargs) tuples to be run.

    variables : A dict of (string, string)
        A dict to be used with format on the layout values

    inventory : An Inventory
        A pointer to an inventory to lookup the objects
    """
    name = None
    description = None
    job_layouts = None
    variables = None
    inventory = None

    def __init__(self, name, job_layouts, inventory=None):
        self.name = name
        self.job_layouts = job_layouts
        self.inventory = None
        self.variables = {}
        self.id = random.randrange(10**2, 10**4)  # FIXME make jobs!

    def timeout(self):
        timeout = None
        if self.inventory:
            timeout = 0
            for layout in self.job_layouts:
                    k = "testsuite"
                    v = layout[k]
                    txt, kwargs = self._parse_toplevel_field_value(k, v)
                    suite = self.inventory.testsuites(txt)
                    timeout += suite.timeout()
        return timeout

    def job_specs(self):
        """Converts the layout into specs.
        The layout contains the strings, here the strings are queried in the
        inventory and objects are created.
        """
        self.variables["planid"] = self.id
        logger.debug("Replacing vars in spec %s: %s" % (self.name, \
                                                        self.variables))
        for layout in self.job_layouts:
            """A generator is used (yield), because a followup spec might
            depend on infos from a previous spec (e.g. a host gets created)
            """
            yield self.spec_from_layout(layout)

    def spec_from_layout(self, layout):
        spec = JobSpec()
        logger.debug("Creating spec for job layout '%s'" % layout)
        for k, func in [("testsuite", self.inventory.testsuites),
                        ("profile", self.inventory.profiles),
                        ("host", self.inventory.hosts),
                        ("additional_kargs", lambda x: x)]:
            kwargs = {}
            if k in layout and layout[k] is not None:
                v, kwargs = self._parse_toplevel_field_value(k, layout[k])
                layout[k] = v
            else:
                layout[k] = ""

            logger.debug("Handling top-level item '%s', with kwargs '%s'" %
                         (k, kwargs))

            item = func(v)

            logger.debug("New item: %s" % item)
            if kwargs and hasattr(item, "__dict__"):
                update_properties_only(item, kwargs)

            props = {k: item}
            spec.update_props(props)
        return spec

    def _parse_toplevel_field_value(self, key, value):
        """Parses the value of a top-level testplan value

        >>> k = "host",
        >>> v = ["the-hostname", {"count": "1", "keep": True, "var": "{VAR}"}]
        >>> p = Testplan("tname", None, None)
        >>> p.variables = {"VAR": "val"}
        >>> p._parse_toplevel_field_value(k, v)
        ('the-hostname', {'count': '1', 'var': 'val', 'keep': True})
        """
        kwargs = {}
        if type(value) is list:
            if len(value) != 2:
                raise RuntimeError(("Expecting the testplan value for '%s' " \
                                    "to be either a single string or a list " \
                                    "with two items (name, additional_" \
                                    "kwarguments), it is: %s") % (key, value))
            value, kwargs = value[0], \
                            {k: v.format(**self.variables) if type(v) in
                             [str, unicode] else v for k, v
                             in value[1].items()}
        value = value.format(**self.variables)

        if any(("{" or "}") in val for val in [value] + kwargs.values()
               if type(val) in [str, unicode]):
            raise Exception(("Variables (%s) could not be substituted " + \
                             "in plan %s: %s / %s") % (self.variables,
                                                       self.name, value,
                                                       kwargs))

        return value, kwargs

    def __str__(self):
        return str(self.__to_dict__())

    def __to_dict__(self):
        return {
                "name": self.name,
                "description": self.description,
                "job_layouts": self.job_layouts,
                "timeout": self.timeout()
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
    description = None

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
            "timeout": self.timeout(),
            "testsets": [t.__to_dict__() for t in self.testsets],
            "libs": self.libs(),
            "description": self.description
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

        >>> import igor.backends.files
        >>> suites = igor.backends.files.Factory.testsuites_from_path( \
                                                           "testcases/suites/")
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
        """Add many testcases to the archive
        """
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
        """Add a single testcase to the archive
        And testcase specififc metadata files
        """
        # Add the testcase itself
        self.__add_data_to_archive(archive, arcname, testcase.source())

        # Add a file with testcase dependencies
        arcdepsname = arcname + ".deps"
        dependencies = "\n".join(testcase.dependencies)
        self.__add_data_to_archive(archive, arcdepsname,
                                   "\n".join(dependencies))

        # Add a testcase extra dir
        testcaseextradir = testcase.filename + ".d"
        if os.path.exists(testcaseextradir):
            logger.debug("Adding extra dir: %s" % testcaseextradir)
            arcname += ".d"
            archive.add(testcaseextradir, arcname=arcname, \
                        recursive=True)

    def __add_data_to_archive(self, archive, arcname, data):
        """Adds data as a file to an archive
        """
        srcobj = io.BytesIO(data)
        info = tarfile.TarInfo(name=arcname)
        info.size = len(srcobj.getvalue())
        info.mtime = time.time()
        archive.addfile(tarinfo=info, fileobj=srcobj)

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
    description = None
    _libs = None
    _testcases = None
    _dependencies = []

    def __init__(self, name, testcases=[], libs=None):
        self.name = name
        self._libs = {}
        self._testcases = []
        self.add(testcases)
        self.libs(libs)
        self._dependencies = []

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
            "timeout": self.timeout(),
            "testcases": [c.__to_dict__() for c in self.testcases()],
            "libs": self.libs()
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
    timeout = 60
    expect_failure = False
    description = None
    dependencies = []

    def __init__(self, filename=None, name=None):
        if name is None and filename is None:
            raise Exception("At least a filename must be given")
        if name is None:
            self.name = os.path.basename(filename)
        else:
            self.name = name
        self.filename = filename
        self.dependencies = []

    def source(self):
        """Returns the source of this testcase
        """
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
                                        dir=session_path)
        os.mkdir(self.__artifacts_path())
        run("chmod -R a+X '%s'" % self.dirname)
        logger.info("Starting session %s in %s" % (self.cookie, self.dirname))

    def remove(self):
        """Remove the session dir and all remaining artifacts
        """
        logger.debug("Removing session '%s'" % self.cookie)

        self.remove_artifacts()

        remaining_files = os.listdir(self.dirname)
        if len(remaining_files) > 0:
            logger.warning("Remaining files for session '%s': %s" % ( \
                                                            self.cookie, \
                                                            remaining_files))
        else:
            logger.debug("Removing testdir '%s'" % self.dirname)
            os.rmdir(self.dirname)

    def remove_artifacts(self):
        logger.info("Removing artifacts")
        for artifact in self.artifacts(use_abs=True):
            logger.debug("Removing artifact '%s'" % artifact)
            try:
                os.remove(artifact)
            except Exception as e:
                logger.warning("Exception while removing '%s': %s" % \
                                                         (artifact, e.message))

    def __artifacts_path(self, name=""):
        """Returns the absoulte path to the artifacts folder
        """
        assert self.dirname is not None
        return os.path.join(self.dirname, "artifacts", name)

    def add_artifact(self, name, data):
        """Adds an artifact
        """
        assert("/" not in name and "\\" not in name)
        afilename = self.__artifacts_path(name)
        # fixme collsisions
        with open(afilename, "wb") as afile:
            afile.write(data)

    def get_artifact(self, name):
        """Returns the data/content of an artifact
        >>> s = TestSession("cookie", "/tmp/")
        >>> s.add_artifact("test", "foo")
        >>> s.get_artifact("test")
        'foo'
        """
        data = None
        afilename = self.__artifacts_path(name)
        if os.path.exists(afilename):
            with open(afilename, "rb") as afile:
                data = afile.read()
        else:
            raise Exception("Artifact '%s' does not exist." % name)
        return data

    def artifacts(self, use_abs=False):
        """Returns a list of all artifacts.
        >>> s = TestSession("cookie", "/tmp/")
        >>> s.add_artifact("test", "")
        >>> s.artifacts()
        ['test']
        """
        dirname = self.__artifacts_path()
        fns = os.listdir(dirname)
        if use_abs:
            fns = [self.__artifacts_path(fn) \
                   for fn in fns]
        return fns

    def get_artifacts_archive(self, selection=None):
        """Return all artifacts as an .tar.bz2
        """
        selection = selection or self.artifacts()
        container = io.BytesIO()
        logger.debug("Preparing artifacts archive for session %s" % \
                                                                   self.cookie)
        with tarfile.open(fileobj=container, mode="w:bz2") as archive:
            for artifact in selection:
                if artifact not in self.artifacts():
                    logger.debug("Artifact not here: %s" % artifact)
                logger.debug("Adding artifact %s" % artifact)
                archive.add(self.__artifacts_path(artifact), artifact)
        return container

    def __enter__(self):
        logger.debug("With session '%s'" % self.cookie)
        return self

    def __exit__(self, _type, value, traceback):
        logger.debug("Ending session %s" % self.cookie)
        if self.do_cleanup:
            self.remove()
        logger.info("Session '%s' ended." % self.cookie)
