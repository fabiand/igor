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

import os
import simplejson as json
from lxml import etree
import utils


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(BASE_PATH, "data")
TRANSFORM_MAP = {
    "job-rst": os.path.join(REPORT_PATH, "job-report.rst.xsl"),
    "job-junit": os.path.join(REPORT_PATH, "job-report.junit.xsl"),
    "testplan-rst": os.path.join(REPORT_PATH, "testplan-report.rst.xsl"),
    "testplan-junit-xml": os.path.join(REPORT_PATH,
                                       "testplan-report.junit.xsl"),
}


def job_status_to_report_json(txt):
    """Apply the plaintext report transformation to a json obj (str)
    """
    d = json.loads(txt)
    return job_status_to_report(d)


def job_status_to_report(d):
    """Transform a job status dict to a report
    """
    return _map_transform(d, "job-rst")


def job_status_to_junit(d):
    """Transform a job status dict to a report
    """
    return _map_transform(d, "job-junit", "job")


def testplan_status_to_report(d):
    """Transform a testplan status dict to a report
    """
    return _map_transform(d, "testplan-rst")


def testplan_status_to_junit_report(d):
    """Transform a testplan status dict to a junit report
    """
    return _map_transform(d, "testplan-junit-xml", "testplan")


def _map_transform(d, t, rootname="status"):
    assert t in TRANSFORM_MAP, "Unknown transformation: %s" % t
    return transform_dict(TRANSFORM_MAP[t], d, rootname)


def transform_dict(stylefile, d, rootname):
    """Apply a transformation to a dict
    """
    xml = utils.obj2xml(rootname, d)
    return transform_xml(stylefile, xml)


def transform_xml(stylefile, xml):
    """Transform an XML Object into another XML objcet using a stylesheet
    """
    transform = etree.XSLT(etree.parse(stylefile))
    report = transform(xml)
    return report


def to_xml_str(etree_obj):
    """Convert a Tree into a str
    """
    return etree.tostring(etree_obj, pretty_print=True)
