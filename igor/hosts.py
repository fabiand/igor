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

import utils
from testing import *
import virt
import testing
import ConfigParser


logger = logging.getLogger(__name__)


class RealHost(GenericHost):
    """Represents a real server.
    Wich is currently just specified by a name and it's MAC address.
    """

    poweron_script = None
    poweroff_script = None

    def prepare(self, session):
        # Not needed with real hosts
        pass

    def start(self):
        logger.debug("Powering on %s: %s" % (self.get_name(), \
                                             utils.run(self.poweron_script)))

    def purge(self):
        logger.debug("Powering off %s: %s" % (self.get_name(), \
                                             utils.run(self.poweroff_script)))

    def __str__(self):
        return "%s <%s>" % (self.name, self.mac)

    def __hash__(self):
        return hash(self)


class RealHostFactory(utils.Factory):
    @staticmethod
    def hosts_from_file(filename, suffix=".hosts"):
        """Reads hosts from a cfg file.

        >>> hosts = RealHostFactory.hosts_from_file("../data/example.hosts")
        >>> hosts["ahost"].mac == "aa:bb:cc:dd:ee"
        True
        """

        if not os.path.isfile(filename):
            raise Exception("Hosts filename does not exist: %s" % filename)

        hostsconfig = ConfigParser.SafeConfigParser()
        hostsconfig.read(filename)
        hosts = {}
        for hostname in hostsconfig.sections():
            host = RealHost()
            props = {"name": hostname}
            for prop in ["mac", "poweron_script", "poweroff_script"]:
                props[prop] = hostsconfig.get(hostname, prop)
            host.__dict__.update(props)
            hosts[hostname] = host
        return hosts

    @staticmethod
    def hosts_from_path(path, suffix=".hosts"):
        """Load hosts form .hosts files in path

        >>> hosts = RealHostFactory.hosts_from_path("../data/")
        >>> hosts["ahost"].mac == "aa:bb:cc:dd:ee"
        True
        """
        if not os.path.exists(path):
            raise Exception("Hosts path does not exist: %s" % path)
        hosts = {}
        pat = os.path.join(path, "*%s" % suffix)
        for f in glob.glob(pat):
            hosts.update(RealHostFactory.hosts_from_file(f))
        return hosts

    @staticmethod
    def hosts_from_paths(paths, suffix=".hosts"):
        """Builds hosts objects by reading them from files in paths

        >>> hosts = RealHostFactory.hosts_from_paths(["../data/"])
        >>> "ahost" in hosts
        True
        """
        hosts = {}
        paths = [str.strip(p) for p in paths]
        for path in paths:
            hosts.update(RealHostFactory.hosts_from_path(path, suffix))
        return hosts


class FilesystemRealHostsOrigin(testing.Origin):
    paths = None

    def __init__(self, paths):
        self.paths = paths

    def name(self):
        return "FilesystemRealHostsOrigin(%s)" % self.paths

    def items(self):
        hosts = RealHostFactory.hosts_from_paths(self.paths)
        for key in hosts:
            hosts[key].origin = self
        return hosts
