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
import logging.config


fs_fileobj = None
__logger = logging.getLogger("")


def configure(fn):
    fs_fileobj = open(fn, "a+")

    log_config = {
        "version": 1,

        "formatters": {
            "default": {
                "format": '%(levelname)-8s - %(asctime)s - ' +
                          '%(name)-15s - %(message)s'
            }
        },

        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
            "filesystem": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": fs_fileobj
            }
        },

        "loggers": {
            "": {
                "handlers": ["console", "filesystem"],
                "level": "DEBUG"
            }
        }
    }

    logging.config.dictConfig(log_config)
    __logger = logging.getLogger("")
    __logger.debug("Configured logging")


def backlog():
    fs_fileobj.flush()
    with open(fs_fileobj.name, "r") as f:
        r = f.read()
    return r

def getLogger(name):
    return __logger.getChild(name)
