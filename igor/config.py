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

import os
import ConfigParser
import logging

logger = logging.getLogger(__name__)


search_paths = [".", "~/.igord", "/etc/igord"]

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def flatten_config(cfg):
    cfgdict = {}
    for section in cfg.sections():
        for name, value in cfg.items(section):
            key = "%s.%s" % (section.lower(), name)
            cfgdict[key] = value
    return cfgdict


def parse_config(fn="igord.cfg"):
    cfg = ConfigParser.SafeConfigParser()
    was_read = False
    for sp in search_paths:
        filename = os.path.join(sp, fn)
        if os.path.exists(filename):
            logger.info("Loading config from '%s'" % filename)
            cfg.read(filename)
            was_read = True
            break
    assert was_read == True, "Config file not found"

    return flatten_config(cfg)
