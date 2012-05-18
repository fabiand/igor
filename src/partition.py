# -*- coding: utf-8 -*-

import logging
import os
import tempfile

from testing import *
from utils import run
from partition import *


class VMImage(Layout):
    pass

class Layout(UpdateableObject):
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
    filename = None
    size = 4
    label = "gpt"
    partitions = [{}]

    def __init__(self, size, partitions, label="gpt", filename=None):
        if not any(size.lower().endswith(s) for s in ["m", "g"]):
            raise Exception("Disk size needs to be suffixed with M or G")
        if label not in ["gpt", "mbr"]:
            raise Exception("Disk label must be gpt or mbr")
        self.filename = filename
        self.size = size
        self.partitions = partitions
        self.label = label

    def create(self, session_dir="/tmp"):
        if self.filename is None:
            self.filename = run("mktemp --tmpdir='%s' 'vmimage-XXXX.img'" % \
                                session_dir)
        logger.debug("Creating VM image '%s'" % self.filename)
        self.truncate()
        self.partition()
        return self.filename

    def remove(self):
        logger.debug("Removing VM image '%s'" % self.filename)
        os.remove(self.filename)

    def truncate(self):
        run("truncate --size=%s '%s'" % (self.size, self.filename))

    def partition(self):
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
                for_parted.append(p.for_parted())

        # Quit parted
        for_parted.append("quit")

        for parted_cmd in for_parted:
            run("parted '%s' '%s'" % (self.filename, parted_cmd))

class Partition(UpdateableObject):
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
    fs_type = ""

    def __init__(self, pt, start, end, fst=""):
        self.part_type = pt
        self.start = start
        self.end = end
        self.fs_type = fst

    def for_parted(self):
        return "mkpart %s %s %s %s" % (self.part_type, self.fs_type, \
                                       self.start, self.end)
