
import unittest
import logging
import os

from gvfs import run

logger = logging.getLogger(__name__)


available_hosts = set()
available_profiles = set()
avialable_testcases = set()


class UpdateableObject(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Host(UpdateableObject):
    profile = None

    def prepare_profile(self, profile):
        raise Exception("Not implemented.")

    def submit_testsuite(self, session, testsuite):
        raise Exception("Not implemented.")


class Profile(UpdateableObject):
    install_kernel_args = None
    kernels_args = None


class Testsuite(UpdateableObject):
    name = None
    profile = None
    testcases = list()


class Testcase(UpdateableObject):
    name = None
    source = None


class TestSession(UpdateableObject):
    dirname = None
    cookie = None

    do_cleanup = False

    def __init__(self, cleanup=True):
        self.do_cleanup = cleanup
        self.cookie = run("date +%Y%m%d-%I%M%S")
        self.dirname = run("mktemp -d '/tmp/test-session-%s-XXXX'" % \
                           self.cookie)
        logger.info("Starting session %s in %s" % (self.cookie, self.dirname))

    def remove(self):
        logger.debug("Removing testdir '%s'" % self.dirname)
        for artifact in self.artifacts():
            logger.debug("Removing artifact '%s'" % artifact)
            os.remove(os.path.join(self.dirname, artifact))
        os.removedirs(self.dirname)

    def artifacts(self, use_abs = False):
        fns = os.listdir(self.dirname)
        if use_abs:
            fns = [os.path.join(self.dirname, fn) \
                   for fn in fns]
        return fns

    def __enter__(self):
        logger.debug("With session '%s'" % self.cookie)
        return self

    def __exit__(self, type, value, traceback):
        logger.debug("Ending session %s" % self.cookie)
        if self.do_cleanup:
            self.remove()
        logger.info("Session '%s' ended." % self.cookie)
