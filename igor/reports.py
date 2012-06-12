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

from lxml import etree
import simplejson as json

import utils

def status_to_report_json(txt):
    """Apply the plaintext report transformation to a json obj (str)
    """
    d = json.loads(txt)
    return status_to_report(d)

def status_to_report(d):
    """Apply the plaintext report transformation to a dict
    """
    return transform_status("../data/tools/report.rst.xsl", d)

def transform_status(stylefile, d):
    """Apply a transformation to a dict
    """
    xml = utils.obj2xml("status", d)
    transform = etree.XSLT(etree.parse(stylefile))
    report = transform(xml)
    return report
