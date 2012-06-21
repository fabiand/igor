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
import logging
import urllib
import re
import tempfile
import shlex
import threading
from lxml import etree

logger = logging.getLogger(__name__)


def run(cmd, with_retval=False):
    import subprocess
    logger.debug("Running: %s" % cmd)
    proc = subprocess.Popen(cmd, shell=True, \
                            stdout=subprocess.PIPE, \
                            stderr=subprocess.PIPE)
    (stdout, stderr) = proc.communicate()
    proc.wait()
    if stderr:
        logger.warning(stderr)
    r = stdout.strip()
    if with_retval:
        r = (proc.returncode, stdout.strip())
    return r


def dict_to_args(d):
    return " ".join(["--%s" % k if v is None else \
                     "--%s=%s" % (k, v) \
                     for k, v in d.items()])


def cmdline_to_dict(cmdline):
    """Simple cmdline parsing.
    Expects key=value pairs.

    Examples:
    >>> cmdline_to_dict("foo=bar")
    {'foo': 'bar'}
    """
    args = {}
    for arg in shlex.split(cmdline):
        key, value = arg.split('=', 1)
        args[key] = value
    return args


class MountedArchive:
    isofilename = None
    mountpoint = None

    def __init__(self, f):
        self.isofilename = f

    def __enter__(self):
        logger.debug("Mounting ISO '%s'" % self.isofilename)
        self.mountpoint = self.mount(self.isofilename)
        return self

    def __exit__(self, type, value, traceback):
        logger.debug("Unmounting ISO: %s" % self.isofilename)
        self.umount()

    def mount(self, iso):
        raise Exception("Not implemented.")

    def umount(self):
        raise Exception("Not implemented.")


class GvfsMountedArchive(MountedArchive):
    def mount(self, iso):
        isobasename = os.path.basename(iso)
        run("gvfs-mount '%s'" % ("archive://file%3a%2f%2f" \
                                 + urllib.quote_plus(iso)))
        self.gvfs_url = self.run(("gvfs-mount -l " \
                                  + "| awk '$2 == \"%s\" {print $4;}'") % \
                                 isobasename)
        return "~/.gvfs/%s/" % isobasename

    def umount(self):
        run("gvfs-mount -u '%s'" % self.gvfs_url)


class LosetupMountedArchive(MountedArchive):
    def mount(self, iso):
        mountpoint = run("mktemp -d /tmp/losetup-XXXX")
        run("mount -oloop '%s' '%s'" % (iso, mountpoint))
        return mountpoint

    def umount(self):
        run("sleep 3 ; umount '%s'" % self.mountpoint)
        os.removedirs(self.mountpoint)


def surl(number):
    import math
    import string
    codes = string.digits[2:] + string.lowercase + string.uppercase
    r = ""
    number = int(number)
    while True:
        key = number % len(codes)
        r += codes[key]
        if number < len(codes) - 1:
            break
        number = int(number / len(codes)) - 1
    return r


class TemporaryDirectory:
    tmpdir = None

    def __enter__(self):
        self.tmpdir = tempfile.mkdtemp()
        return self.tmpdir

    def __exit__(self, type, value, traceback):
        os.rmdir(self.tmpdir)


def scanf(pat, txt):
    #http://docs.python.org/library/re.html#simulating-scanf
    regex = pat
    for (a, b) in [("%s", "(\S+)"), ("%d", "([-+]?\d+)")]:
        regex = regex.replace(a, b)
    r = re.search(regex, txt)
    return r.groups()


def synchronized(lock):
    """ Synchronization decorator. """
    def wrap(f):
        def newFunction(*args, **kw):
#            logger.debug("Acq %s, %s" % (f, lock))
            lock.acquire()
            try:
                return f(*args, **kw)
            finally:
#                logger.debug("Rel %s, %s" % (f, lock))
                lock.release()
        return newFunction
    return wrap


def xor(a, b):
    return bool(a) ^ bool(b)


def parse_bool(s):
    """Parse a bool from string

    >>> all([ parse_bool(s) for s in ["yes", "Yes", "y", "true", "True", 1] ])
    True
    """
    return str(s).lower()[0] in ["t", "1", "y"]


class PollingWorkerDaemon(threading.Thread):
    interval = None
    _stop_event = None

    def __init__(self, interval=10):
        self.interval = interval
        self._stop_event = threading.Event()
        threading.Thread.__init__(self)
        self.daemon = True

    def _debug(self, msg):
        logger.debug("[%s] %s" % (self, msg))

    def run(self):
        self._debug("Starting")
        keep_running = True
        while keep_running:
            self.work()
            if self.is_stopped():
                self._debug("Stopping")
                keep_running = False
            self._stop_event.wait(self.interval)
        self._debug("Ending")

    def stop(self):
        self._debug("Requesting worker stop")
        self._stop_event.set()

    def is_stopped(self):
        return self._stop_event.is_set()

    def work(self):
        """Call self.stop() to end
        """
        raise Exception("Not implemented")


class State(object):
    name = None
    map = None

    def __init__(self, n):
        self.name = n

    def transition(self, input):
        next_states = [s for f, s in self.map if f(input)]
        assert len(next_states) >= 1, "faulty transition rule"
        return next_states[0]

    def __str__(self):
        return "%s" % (self.name)

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return not (self == other)


def obj2xml(root, obj):
    """Simple dict2xml mechanism

    >>> a = {"abc": "ah", "b": { "one": 1, "two": "<2>" }, "c": [10,20,30]}
    >>> root = obj2xml("root", a)
    >>> print(etree.tostring(root, pretty_print=True)).strip()
    <root>
      <c>10</c>
      <c>20</c>
      <c>30</c>
      <abc>ah</abc>
      <b>
        <two>&lt;2&gt;</two>
        <one>1</one>
      </b>
    </root>
    """
    if type(root) == str:
        root = etree.Element(root)
    if type(obj) == list:
        for v in obj:
            root.append(obj2xml(root.tag, v))
    elif type(obj) == dict:
        for k, v in obj.items():
            if type(v) == list:
                items = obj2xml(k, v)
                root.extend(items)
            else:
                root.append(obj2xml(k, v))
    else:
        root.text = str(obj)
    return root


class Factory(object):
    """A factory to build testing objects from different structures.
    The current default structure is a file/-system based approach.
    Files provide enough informations to build testsuites.
    """

    @staticmethod
    def _from_file(filename, cb_map):
        """Reads a file and calls a callback per line.
        This provides some functionality like ignoring comments and blank
        lines.

        cb_map is a map of {selector: cb}, where the selector is determind by
        the pattern "^([^:]+):" on each line, e.g.:
            lib:common      # Selector: lib     >>   Callback: lib
            tc.should       # selector: (None)  >>   Callback: None (default)
        """
        objs = []
        if not os.path.exists(filename):
            raise Exception("Can't find %s rel. to %s" % (filename, \
                                                          os.getcwd()))
        with open(filename, "r") as f:
            for line in f:
                line = re.sub("\s*#.*$", "", line).strip()
                if line == "":
                    continue
                cb, line = Factory._selector_based_cb_from_line(line, cb_map)
                obj = cb(line)
                if obj:
                    objs.append(obj)
        return objs

    @staticmethod
    def _selector_based_cb_from_line(line, cbmap):
        """Parse a selector from a string.
        If cbmap is a map, then the None entry is taken as the default selector

        Example:
        >>> def rcb(txt, cbm):
        ...     cb, ntxt = Factory._selector_based_cb_from_line(txt, cbm)
        ...     return cb(ntxt)

        >>> cbmap = {}
        >>> cbmap[None] = lambda x: ("default", x)
        >>> cbmap["lib"] = lambda x: ("lib", x)

        >>> rcb("lib:common", cbmap)
        ('lib', 'common')

        >>> rcb("tc", cbmap)
        ('default', 'tc')
        """
        cb = None
        if type(cbmap) is dict:
            selector_pat = re.compile("^([^:]+):")
            sel = None
            if selector_pat.match(line):
                sel = selector_pat.match(line).groups()[0]
                line = selector_pat.sub("", line)
            if sel not in cbmap:
                raise Exception("Unknown selector '%s'" % sel)
            cb = cbmap[sel]
        else:
            raise Exception("Not mapable: %s (%s)" % (cbmap, type(cbmap)))
        return (cb, line)
