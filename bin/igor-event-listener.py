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

from lxml import etree
import junitless
import socket
import sys
import tempfile
import urllib2
import shutil


REMOTE=sys.argv[1]
PORT=8090
REPORTBASE="http://{host}:{port}/jobs/{sessionid}/status?format=xml"

def follow_events(server, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server, port))
    sf = sock.makefile()
    for line in sf:
        event = etree.XML(line)
        if event.attrib:
            yield event.attrib

def retrieve_report(sessionid):
    url = REPORTBASE.format(host=REMOTE, port="8080", sessionid=sessionid)
    print "Fetching %s" % url
    #urllib2.urlopen(url)
    with tempfile.NamedTemporaryFile() as tmpfile:
        shutil.copyfile("/home/fdeutsch/dev/ovirt/igor/daemon/igor/data/st.junit.xml", tmpfile.name)
        #  xsltproc report.junit.xsl st.xml | tee st.junit.xml
        junitless.clearscreen()
        builder = junitless.LogBuilder()
        builder.from_file(tmpfile.name)
        builder.log.writeln(junitless.ansi("Waiting ...").white)

for evnt in follow_events(REMOTE, PORT):
    retrieve_report(evnt["session"])
