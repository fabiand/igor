# -*- coding: utf-8 -*-
#
# Copyright (C) 2013  Red Hat, Inc.
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

#
# DESCRTIPTION
#

from igor import reports
from lxml import etree
import socket
import sys

REPORTBASE = "http://{host}:{port}/jobs/{sessionid}/status?format=xml"


def follow_events(server, port):
    family = socket.AF_INET6 if ":" in server else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.connect((server, int(port)))
    sf = sock.makefile()
    for line in sf:
        event = etree.XML(line)
        if event.attrib:
            yield event.attrib
    sf.close()


def __FIXME_retrieve_report(remote, port, sessionid):
    url = REPORTBASE.format(host=remote, port=port, sessionid=sessionid)
    print("Fetching %s" % url)
    #statusdata = urllib2.urlopen(url).read()
    _statusfile = "/home/fdeutsch/dev/ovirt/igor/daemon/igor/data/st.xml"
    #_junitfile = "/home/fdeutsch/dev/ovirt/igor/daemon/igor/data/st.junit.xml"
    statusdata = open(_statusfile).read()

    xsltfile = reports.TRANSFORM_MAP["job-junit"]
    statusxml = etree.XML(statusdata)
    junitxml = reports.transform_xml(xsltfile, statusxml)
    junitdata = reports.to_xml_str(junitxml)

    return junitdata


if __name__ == "__main__":
    remote = sys.argv[1]
    port = 8090
    for evnt in follow_events(remote, port):
        __FIXME_retrieve_report(remote, port, evnt["session"])
