#!/bin/env python

import json
import os
import sys
import base64
import logging
import logging.config
import time
import re
import bottle
from string import Template

from testing import *
from virt import *
from cobbler import Cobbler
from job import *
import utils

from config import *

#logging.config.fileConfig("logconf.ini")
logging.basicConfig( \
    format='%(levelname)s - %(module)s - %(asctime)s - %(message)s', \
    level=logging.DEBUG)
logger = logging.getLogger(__name__)

IGORDDIR=sys.path[0]

jc = JobCenter(session_path=SESSION_PATH)
cobbler = Cobbler(COBBLER_URL, COBBLER_CREDENTIALS)

def load_testsuites():
    return Factory.testsuites_from_path(TESTCASES_PATH)

def create_cobbler_profile(pname):
    """This is actually creating a cobbler system, in cobbler terms
    """
    return cobbler.new_profile(pname, {
      "kernel_options": " ".join([COBBLER_KARGS, COBBLER_KARGS_INSTALL]),
      "kernel_options_post": COBBLER_KARGS,
      })

class IgordJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Job) or isinstance(obj, Testsuite) or \
           isinstance(obj, Testset) or isinstance(obj, Testcase):
            return obj.__json__()
        elif isinstance(obj, utils.State):
            return str(obj)
        return json.JSONEncoder.default(self, obj)

def to_json(obj):
    bottle.response.content_type = "application/json"
    return json.dumps(obj, cls=IgordJSONEncoder, sort_keys=True, indent=2)

def _req_cookie():
    cookie_key = "x-igor-cookie"
    if cookie_key not in bottle.request.headers:
        bottle.abort("Cookie missing")
    cookie = bottle.request.headers[cookie_keys]
    if cookie not in jc.open_jobs:
        bottle.abort("Unknown job")
    return cookie

#
# bottles

@bottle.route('/submit/<testsuite>/with/<profile>/on/<host>', method='GET')#
@bottle.route('/submit/<testsuite>/with/<profile>/on/<host>/<cookiereq>', method='GET')
def submit_testsuite(testsuite, profile, host, cookiereq=None):
    host = VMHostFactory.create_default_host( \
        connection_uri=LIBVIRT_CONNECTION_URI, \
        storage_pool=LIBVIRT_STORAGE_POOL,
        network_configuration=LIBVIRT_NETWORK_CONFIGURATION)
    logger.warning("We are currently using a default host")

    testsuites = load_testsuites()
    logger.debug("Loaded testsuites: %s" % testsuites)
    if testsuite not in testsuites:
        bottle.abort(412, "Unknown testsuite '%s'" % testsuite)

    logger.debug("Starting cobbler session")
    with cobbler.new_session() as cblr_sess:
        logger.debug("Checking profile %s" % profile)
        if profile not in cblr_sess.get_profiles():
            bottle.abort(412, "Unknown profile '%s'" % profile)

    logger.debug("Checks done, submitting testsuite")
    resp = jc.submit_testsuite(testsuites[testsuite], \
                               create_cobbler_profile(profile), \
                               host, cookiereq)
    return to_json(resp)

@bottle.route('/jobs', method='GET')
def get_jobs():
    return to_json(jc.get_jobs())

@bottle.route('/job/start/<cookie>', method='GET')
def start_job(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    m = jc.start_job(cookie)
    return to_json(m)

@bottle.route('/job/status/<cookie>', method='GET')
def job_status(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    m = jc.jobs[cookie]
    return to_json(m)

@bottle.route('/job/step/<cookie>/<n:int>/<result:re:success|failed>', method='GET')
def finish_step(cookie, n, result):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    note = None
    m = jc.finish_test_step(cookie, n, result == "success", note)
    return to_json(m)

@bottle.route('/job/abort/<cookie>', method='GET')
@bottle.route('/job/abort/<cookie>/<clean>', method='GET')
def abort_job(cookie, clean=False):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    try:
        m = jc.abort_job(cookie)
    except Exception as e:
        m = e.message
    if clean:
        jc.end_job(cookie)
    return to_json(m)

@bottle.route('/job/end/<cookie>', method='GET')
def end_job(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    try:
        m = jc.end_job(cookie)
    except Exception as e:
        m = e.message
    return to_json(m)

@bottle.route('/job/testsuite/for/<cookie>', method='GET')
def get_testsuite_archive(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    t = jc.jobs[cookie].testsuite
    r = t.get_archive()
    if not r:
        bottle.abort(404, 'No testsuite for %s' % (cookie))

    return r.getvalue()

@bottle.route('/job/artifact/for/<cookie>/<name>', method='PUT')
def add_artifact(cookie, name):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    if "/" in name:
        bottle.abort(412, "Name may not contain slashes")
    j = jc.jobs[cookie]
    j.add_artifact(name, bottle.request.body.read())

@bottle.route('/job/artifact/from/<cookie>', method='GET')
def get_artifacts(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    j = jc.jobs[cookie]
    return j.get_artifacts_archive().getvalue()

@bottle.route('/firstboot/<cookie>', method='GET')
@bottle.route('/job/<cookie>/set/enable_pxe/<enable_pxe>', method='GET')
def disable_pxe_cb(cookie, enable_pxe=False):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    j = jc.jobs[cookie]
    m = j.profile.enable_pxe(enable_pxe)
    return to_json(m)

@bottle.route('/job/<cookie>/set/kernelargs/<kernelargs>', method='GET')
def set_kernelargs_cb(cookie, kernelargs):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    raise Exception("Not implemented yet, but needed for updates")
    j = jc.jobs[cookie]
    m = j.profile.set_kargs(j.host.get_name(), kernelargs)
    return to_json(m)


@bottle.route('/testjob/<cookie>', method='GET')
def get_bootstrap_script(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)

    disable_pxe_cb(cookie)

    script = None

    with open("testsuite-client.sh", "r") as f:
        script = f.read()

    r = Template(script).safe_substitute(
        igor_cookie=cookie,
        igor_current_step=jc.jobs[cookie].current_step,
        igor_testsuite=jc.jobs[cookie].testsuite.name
    )

    if not r:
        bottle.abort(404, 'No testsuite for %s' % (cookie))

    return r

@bottle.route('/static/data/<filename>')
def static_data(filename):
    return bottle.static_file(filename, root=os.path.join(IGORDDIR, "..", "data"))

@bottle.route('/testsuite/<name>', method='GET')
def get_testsuite_archive(name):
    testsuites = load_testsuites()
    t = testsuites[name]
    r = t.get_archive()
    if not r:
        bottle.abort(404, 'No testsuite for %s' % (cookie))

    return r.getvalue()

if REMOTE_COBBLER_PROFILE_CREATION_ENABLED:
    logger.info("Enabling remote ISO management for cobbler")

    @bottle.route('/extra/profile/add/<pname>/iso/<isoname>/remote', method='GET')
    def add_iso_profile_remote(pname, isoname):
        retval = 0
        with utils.TemporaryDirectory() as tmpdir:
            cmd = """
    curl -v "{baseurl}/{isoname}" --output "{isoname}"
    [[ -e "{isoname}" ]] || ( echo NO {isoname} ; exit 1; )

    export KOPTS="{kopts}" # To reduce the number of opts
    bash "{igorddir}/../data/cobbler_iso_tool.sh" remote_add "{sshuri}" "{profilename}" "{isoname}"
    RETVAL=$?
    rm -f "{isoname}"
    exit $RETVAL
    """.format( \
            igorddir=sys.path[0], \
            tmpdir=tmpdir, \
            baseurl=REMOTE_COBBLER_PROFILE_CREATION_BASE_URL, \
            sshuri=REMOTE_COBBLER_PROFILE_CREATION_SSH_URI, \
            profilename=pname, \
            isoname=isoname,
            kopts=REMOTE_COBBLER_PROFILE_KOPTS)
            retval, stdout = run(cmd, with_retval=True)
        return to_json((retval, stdout))

    @bottle.route('/extra/profile/remove/<pname>/remote', method='GET')
    def remove_iso_profile_remote(pname):
        retval = 0
        with utils.TemporaryDirectory() as tmpdir:
            cmd = """
    bash "{igorddir}/../data/cobbler_iso_tool.sh" remote_remove "{sshuri}" "{profilename}"
    exit 0
    """.format( \
            igorddir=IGORDDIR, \
            tmpdir=tmpdir, \
            sshuri=REMOTE_COBBLER_PROFILE_CREATION_SSH_URI, \
            profilename=pname)
            retval, stdout = run(cmd, with_retval=True)
        return to_json((retval, stdout))


if __name__ == "__main__":
    try:
    #    logger.info("Starting igord")
        bottle.run(host='0.0.0.0', port=8080, reloader=True)
    except KeyboardInterrupt:
        logger.debug("Cleaning")
        jc.clean()



