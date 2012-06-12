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
TRANSFORM_MAP = {
    "rst": os.path.join(BASE_PATH, "data", "report.rst.xsl")
}


def status_to_report_json(txt):
    """Apply the plaintext report transformation to a json obj (str)
    """
    d = json.loads(txt)
    return status_to_report(d)


def status_to_report(d, t="rst"):
    """Apply the plaintext report transformation to a dict
    """
    assert t in TRANSFORM_MAP, "Unknown transformation: %s" % t
    return transform_status(TRANSFORM_MAP[t], d)


def transform_status(stylefile, d):
    """Apply a transformation to a dict
    """
    xml = utils.obj2xml("status", d)
    transform = etree.XSLT(etree.parse(stylefile))
    report = transform(xml)
    return report
