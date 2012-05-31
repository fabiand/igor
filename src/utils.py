# -*- coding: utf-8 -*-

import os
import logging
import urllib
import re

logger = logging.getLogger(__name__)


def run(cmd):
    import subprocess
    logger.debug("Running: %s" % cmd)
    proc = subprocess.Popen(cmd, shell=True, \
                            stdout=subprocess.PIPE, \
                            stderr=subprocess.PIPE)
    (stdout, stderr) = proc.communicate()
    proc.wait()
    if proc.returncode != 0:
        raise Exception(proc.returncode, stderr)
    if stderr:
        logger.warning(stderr)
    r = stdout.strip()
    return r


def dict_to_args(d):
    return " ".join(["--%s" % k if v is None else \
                     "--%s=%s" % (k, v) \
                     for k, v in d.items()])


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
    import math, string
    codes = string.digits[2:] + string.lowercase + string.uppercase
    r = ""
    number = int(number)
    while True:
        key = number % len(codes)
        r += codes[key]
        if number < len(codes)-1:
            break
        number = int(number / len(codes)) - 1
    return r

def scanf(pat, txt):
    #http://docs.python.org/library/re.html#simulating-scanf
    regex = pat
    for (a, b) in [ ("%s", "(\S+)"), ("%d", "([-+]?\d+)") ]:
        regex = regex.replace(a, b)
    r = re.search(regex, txt)
    return r.groups()

def synchronized(lock):
    """ Synchronization decorator. """
    def wrap(f):
        def newFunction(*args, **kw):
            lock.acquire()
            try:
                return f(*args, **kw)
            finally:
                lock.release()
        return newFunction
    return wrap

class State(object):
    name = None
    map = None
    def __init__(self, n):
        self.name = n
    def transition(self, input):
        next_states = [ s for f, s in self.map if f(input)  ]
        assert len(next_states) >= 1, "faulty transition rule"
        return next_states[0]
    def __str__(self):
        return "%s" % (self.name)
    def __eq__(self, other):
        return str(self) == str(other)
    def __ne__(self, other):
        return not (self == other)
