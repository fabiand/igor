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
from igor import log
import igor.main
import igor.partition
from igor.utils import run

logger = log.getLogger(__name__)


class DiskImage(igor.main.UpdateableObject):
    filename = None
    size = None
    format = None

    def __init__(self, filename, size, format):
        if not any(size.lower().endswith(s) for s in ["m", "g"]):
            raise Exception("Disk size needs to be suffixed with M or G")
        self.filename = filename
        self.size = size
        self.format = format


class Layout(DiskImage):
    '''
    An image specififcation for a VMHost.
    This are actually params for truncate and parted.

    Parameters
    ----------
    size : int-like
        Size in GB
    label : string, optional
        label in ['gpt', 'mbr', 'loop']
    partitions : Array of Partitions
    '''
    label = None
    partitions = None

    def __init__(self, size, partitions, label="gpt", filename=None):
        super(Layout, self).__init__(filename, size or 4, "raw")
        if label not in ["gpt", "mbr"]:
            raise Exception("Disk label must be gpt or mbr")
        self.partitions = partitions or [{}]
        self.label = label

    def create(self, session_dir):
        if self.filename is None:
            self.filename = run("mktemp --tmpdir='%s' 'vmimage-XXXX.img'" %
                                session_dir)
        logger.debug("Creating VM image '%s'" % self.filename)
        self.__truncate()
        self.__partition()
        return self.filename

    def remove(self):
        logger.debug("Removing VM image '%s'" % self.filename)
        os.remove(self.filename)

    def __truncate(self):
        run("truncate --size=%s '%s'" % (self.size, self.filename))

    def __partition(self):
        for_parted = []

        # Create label
        if self.label not in ['gpt', 'mbr', 'loop']:
            raise Exception("No valid label given.")
        for_parted.append("mklabel %s" % self.label)

        # Create all partitions
        if self.partitions is None or len(self.partitions) is 0:
            logger.debug("No partitions given")
        else:
            for p in self.partitions:
                for_parted.append(p.__to_parted__())

        # Quit parted
        for_parted.append("quit")

        for parted_cmd in for_parted:
            run("parted '%s' '%s'" % (self.filename, parted_cmd))


class Partition(igor.main.UpdateableObject):
    '''
    Params
    ------
    An array of dicts containing:
    - part_type (pri, sec, ext)
    - fs_type (ext[234], btrfs, ...), optional
    - start (see parted)
    - end (see parted)
    '''
    part_type = None
    start = None
    end = None
    fs_type = None

    def __init__(self, pt, start, end, fst=""):
        self.part_type = pt
        self.start = start
        self.end = end
        self.fs_type = fst

    def __to_parted__(self):
        return "mkpart %s %s %s %s" % (self.part_type, self.fs_type,
                                       self.start, self.end)
