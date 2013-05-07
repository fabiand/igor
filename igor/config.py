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

import log
import os
import pprint
import yaml

logger = log.getLogger(__name__)


search_paths = [".", "~/.igord", "/etc/igord"]

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def locate_config_file(fn="igord.cfg"):
    filename = None
    for sp in search_paths:
        _filename = os.path.join(sp, fn)
        if os.path.exists(_filename):
            filename = _filename
            break

    if not filename:
        raise RuntimeError("No configuration file found in %s" % search_paths)

    return filename


def parse_config(fn="igord.cfg", updates=None):
    filename = locate_config_file(fn)
    logger.info("Loading config from: %s" % filename)
    with open(filename) as src:
        config = yaml.load(src.read())

    logger.debug("Config: %s" % pprint.pformat(config))

    if updates:
        logger.debug("Config updates: %s" % updates)
        update_by_path(config, updates)

    return config


def set_by_path(store, paths, value):
    """Sets the element path in store to value (or appends it, if a list)
    """
    path, paths = paths[0], paths[1:]
    if paths:
        return set_by_path(store[path], paths, value)
    if type(store[path]) is list:
        store[path].append(value)
    else:
        store[path] = value
    return store[path]


def update_by_path(config, paths_n_values):
    """Update a config dict by paths and value tuples
    Args:
        config: A nested dict like parse_config returns
        paths_n_values: [(path, value), ...]
            Where path is "/" separated
    """
    for path, val in paths_n_values:
        paths = path.split("/")
        set_by_path(config, paths, val)
