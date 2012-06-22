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


logger = logging.getLogger(__name__)


class RealHost(Host):
  @staticmethod
  def from_line(line):
    # <hostname> <mac> …
    token = line.split()
    token.reverse()
    assert len(token) > 1, "Hostname and MAC are mandatory"
    hostname = token.pop()
    mac = token.pop()
    c = RealHost(hostname, mac)
    return c

  def __str__(self):
    return "%s <%s>" % (self.name, self.mac)

  def __hash__(self):
    return str(self)


class RealHostFactory(utils.Factory):
  def hosts_from_file(filename, suffix=".hosts"):
    name = os.path.basename(filename).replace(suffix, "")
    searchpath = os.path.dirname(filename)
    cases = RealHostFactory._from_file(filename, {
      None: lambda line: RealHost.from_line(os.path.join(searchpath, line))
    })
    return Testset(name=name, testcases=cases)

class HostInventory(object):
  def host_from_name(name):
    pass


# vim: sw=2:
