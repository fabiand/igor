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
    { "foo": "bar" }
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

def dict2xml(d, rootname="items"):
    """Simple dict2xml mechanism

    >>> a = {"a": "ah", "<b>": { "1": 1, "2": 2 } }
    >>> print(etree.tostring(dict2xml(a, "root"), pretty_print=True))
<root>
  <item key="a">ah</item>
  <item key="&lt;b&gt;">
    <items>
      <item key="1">1</item>
      <item key="2">2</item>
    </items>
  </item>
</root>

    """
    root = etree.Element(rootname)
    for k, v in d.items():
        node = etree.Element("item")
        node.attrib["key"] = str(k)
        if type(v) == dict:
            node.append(dict2xml(v))
        else:
            node.text = str(v)
        root.append(node)
    return root
