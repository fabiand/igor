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

import sys
import os.path
from lxml import etree
import simplejson as json

import reports

def xs(xml):
    return etree.tostring(xml, pretty_print=True)

def main():
    if len(sys.argv) < 2:
        raise Exception("No status file given.")

    filename = sys.argv[1]
    fp = None

    if filename == "-":
        fp = sys.stdin

    elif os.path.exists(filename):
        fp = open(filename)

    else:
        raise Exception("Status file does not exist.")

    txt = fp.read()

    print(reports.status_to_report_json(txt))

def usage():
    print "Usage: %s <status.json-file>" % sys.argv[0]

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        sys.stderr.write("ERROR: %s\n" % e.message)
        usage()
