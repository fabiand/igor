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

import logging
import os
import glob
import yaml

import igor.main
import igor.utils
import igor.backends.libvirt


logger = logging.getLogger(__name__)


class Host(igor.main.Host):
    """Represents a real server.
    Wich is currently just specified by a name and it's MAC address.
    """

    name = None
    mac = None

    poweron_script = None
    poweroff_script = None

    def prepare(self):
        # Not needed with real hosts
        pass

    def get_name(self):
        return self.name

    def get_mac_address(self):
        return self.mac

    def start(self):
        logger.debug("Powering on %s: %s" % (self.get_name(), \
                                          igor.utils.run(self.poweron_script)))

    def purge(self):
        logger.debug("Powering off %s: %s" % (self.get_name(), \
                                         igor.utils.run(self.poweroff_script)))

    def __str__(self):
        return "%s <%s>" % (self.get_name(), self.get_mac_address())

    def __hash__(self):
        return hash(str(self))


class HostsOrigin(igor.main.Origin):
    paths = None

    def __init__(self, paths):
        self.paths = paths

    def name(self):
        return "FilesystemRealHostsOrigin(%s)" % self.paths

    def items(self):
        hosts = Factory.hosts_from_paths(self.paths)
        for key in hosts:
            hosts[key].origin = self
        return hosts


class TestsuitesOrigin(igor.main.Origin):
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


class TestplansOrigin(igor.main.Origin):
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


class Factory(igor.utils.Factory):
    """A factory to build testing objects from different structures.
    The current default structure is a file/-system based approach.
    Files provide enough informations to build testsuites.
    """

    @staticmethod
    def testplan_from_file(filename, suffix=".plan"):
        """Builds a Testplan from a testplan file.
        The *.plan files are yaml encoded files containing the fields
        (testsuite, profile, host) for each job to be run in the plan.

        A sample tesplan could look like:
            --- # Testplan properties
            description: A simple plan

            # Now the jobs
            ---
            testsuite: 'basic_tui_installation'
            profile: '{profile_pri}'
            host: 'default-libvirt'
            additional_kargs: 'foo'
            ---
        """
        documents = Factory.__read_yaml(filename)
        layout_fields = ["testsuite", "profile", "host"]  # kargs

        properties, layouts = (documents[0],
                               [d for d in documents[1:] if d != None])

        assert all([set(layout_fields) - set(l.keys()) == set([])
                    for l in layouts])
        name = os.path.basename(filename).replace(suffix, "")
        plan = igor.main.Testplan(name=name, job_layouts=layouts)
        plan.__dict__.update(properties)

        return plan

    @staticmethod
    def testplans_from_paths(paths, suffix=".plan"):
        """Builds a dict of testplans from *.plans files in a path.
        A filesystem layout could look like:
            suites/basic.plan
            suites/advanced.plan
        This would create a dict with two plans basic and advanced.

        >>> plans = Factory.testplans_from_paths(["testcases/"])
        >>> "exampleplan" in plans
        True

        >>> plan = plans["exampleplan"]
        >>> plan.name == "exampleplan"
        True
        >>> "auto-installation" in plan.description
        True
        >>> plan.timeout() is None  # Calculated by jobspecs()
        True
        """
        assert type(paths) is list
        plans = {}
        for path in paths:
            if not os.path.exists(path):
                raise Exception("Testplan path does not exist: %s" % path)
            pat = os.path.join(path, "*%s" % suffix)
#            logger.debug("Loading plan from %s" % pat)
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

        >>> suites = Factory.testsuites_from_path("testcases/suites/")
        >>> suites["examplesuite"].libs()
        {'common': 'testcases/libs/common'}
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

        >>> suites = Factory.testsuites_from_paths(["testcases/suites/"])
        >>> "examplesuite" in suites
        True
        >>> suite = suites["examplesuite"]
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
            ---
            description: "An example testsuite"

            # Now the sets, each block can have optionally a searchpath
            ---
            searchpath: '../sets/'
            sets:
              - 'example.set'
              - 'selinux.set'
        """

        documents = Factory.__read_yaml(filename)
#        set_fields = ["sets"]  # searchpath

        properties, blocks = (documents[0],
                              [d for d in documents[1:] if d != None])

        sets = []
        testsuitedir = os.path.dirname(filename)
        for block in blocks:
            searchpath = "."
            if "searchpath" in block:
                searchpath = block["searchpath"]
            for tset in block["sets"]:
                tsetfn = os.path.join(testsuitedir, searchpath, tset)
                tsetfn = os.path.relpath(os.path.realpath(tsetfn))
                testset = Factory.testset_from_file(tsetfn)
                sets.append(testset)

        name = os.path.basename(filename).replace(suffix, "")
        suite = igor.main.Testsuite(name=name, testsets=sets)
        suite.__dict__.update(properties)

        return suite

    @staticmethod
    def testset_from_file(filename, suffix=".set"):
        """Builds a Testset from a testset file.
        The *.set files are expected to contain one testcase file and
        optionally some arguments per line.
        The testcase files path is relative to the testset file.

        Example of a testset file:
            ---
            description: 'Some selinux related tests'
            searchpath: '../tcs/'
            libs: []

            ---
            filename: 'selinux-denials.py'
            expect_failure: True
            ---

        """
        testsetdir = os.path.dirname(filename)
        documents = Factory.__read_yaml(filename)

        properties, layouts = (documents[0],
                               [d for d in documents[1:] if d != None])

        searchpath = "."
        if "searchpath" in properties:
            searchpath = properties["searchpath"]

        libs = []
        if "libs" in properties:
            libs = properties["libs"]
            libs = [os.path.relpath(os.path.join(testsetdir, l)) for l in libs]

        cases = []
        for l in layouts:
            tcasefn = os.path.join(testsetdir, searchpath, l["filename"])
            tcasefn = os.path.relpath(os.path.realpath(tcasefn))
            testcase = igor.main.Testcase(filename=tcasefn)
            del l["filename"]
            testcase.__dict__.update(l)
            cases.append(testcase)

        name = os.path.basename(filename).replace(suffix, "")
        return igor.main.Testset(name=name, testcases=cases, libs=libs)

    @staticmethod
    def hosts_from_file(filename, suffix=".hosts"):
        """Reads hosts from a cfg file.

        >>> hosts = Factory.hosts_from_file("data/example.hosts")
        >>> hosts["ahost"].mac == "aa:bb:cc:dd:ee"
        True
        """

        if not os.path.isfile(filename):
            raise Exception("Hosts filename does not exist: %s" % filename)

        host_fields = ["name", "mac", "poweron_script", "poweroff_script"]
        default_key = "DEFAULT"

        data = open(filename).read()
        documents = yaml.load_all(data)
        hosts = {}
        # Read hosts from file
        for document in documents:
            host = Host()
            host.__dict__.update(document)
            hosts[host.name] = host

        # Gather defaults from default host
        if default_key in hosts.keys():
            default_host = hosts[default_key]
            for host in hosts.values():
                missing_fields = set(host_fields) - set(host.__dict__.keys())
                defaults = {k: default_host.__dict__[k]
                            for k in missing_fields}
                host.__dict__.update(defaults)
                assert all([f in document.keys() for f in host_fields])
            # Remove default host from list
            del hosts[default_key]

        return hosts

    @staticmethod
    def hosts_from_path(path, suffix=".hosts"):
        """Load hosts form .hosts files in path

        >>> hosts = Factory.hosts_from_path("data/")
        >>> hosts["ahost"].mac == "aa:bb:cc:dd:ee"
        True
        """
        if not os.path.exists(path):
            raise Exception("Hosts path does not exist: %s" % path)
        hosts = {}
        pat = os.path.join(path, "*%s" % suffix)
        for f in glob.glob(pat):
            hosts.update(Factory.hosts_from_file(f))
        return hosts

    @staticmethod
    def hosts_from_paths(paths, suffix=".hosts"):
        """Builds hosts objects by reading them from files in paths

        >>> hosts = Factory.hosts_from_paths(["data/"])
        >>> "ahost" in hosts
        True
        """
        hosts = {}
        paths = [str.strip(p) for p in paths]
        for path in paths:
            hosts.update(Factory.hosts_from_path(path, suffix))
        return hosts
