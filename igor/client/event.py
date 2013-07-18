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

from igor import reports, common
from lxml import etree
import logging
import sys
import redis

REPORTBASE = "http://{host}:{port}/jobs/{sessionid}/status?format=xml"


def follow_events(server, port):
    r = redis.Redis(host=server, port=int(port))
    p = r.pubsub()
    p.subscribe(common.REDIS_EVENTS_PUBSUB_CHANNEL_NAME)
    for obj in p.listen():
        event = None
        xmlstr = str(obj["data"]).strip()
        if not xmlstr.startswith("<"):
            # Sometimes just an int is sent ...
            continue
        try:
            event = etree.XML(xmlstr)
        except:
            logging.exception("Failed to parse: %s -> %s" % (obj, xmlstr))
        if event is not None and event.attrib:
            yield event.attrib
    p.unsubscribe(common.REDIS_EVENTS_PUBSUB_CHANNEL_NAME)
    p.close()


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
