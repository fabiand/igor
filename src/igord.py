#!/bin/env python

import json
import os
import base64
import logging
import time
import bottle
import bottle
from string import Template

from testing import *
from virt import *
from cobbler import Cobbler
from job import *
import utils
import example
import testsuites

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

jc = JobCenter(filename="jc.data", autosave=False)


class StatemachineEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Job) or isinstance(obj, Testsuite) or \
           isinstance(obj, Testset) or isinstance(obj, Testcase):
            return obj.__json__()
        elif isinstance(obj, utils.State):
            return str(obj)
        return json.JSONEncoder.default(self, obj)

def to_json(obj):
    bottle.response.content_type = "application/json"
    return json.dumps(obj, cls=StatemachineEncoder, sort_keys=True, indent=2)

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
#
@bottle.route('/jobs', method='GET')
def get_jobs():
    return to_json(jc.get_jobs())

@bottle.route('/job/submit/<testsuite>/with/<profile>/on/<host>/<cookiereq>', method='GET')
def submit_testsuite(testsuite, profile, host, cookiereq=None):
    resp = jc.submit_testsuite(testsuites.simple, example.profile, \
                               example.host, cookiereq)
    return to_json(resp)

@bottle.route('/job/start/<cookie>', method='GET')
def start_job(cookie):
    m = jc.start_job(cookie)
    return to_json(m)

@bottle.route('/job/status/<cookie>', method='GET')
def job_status(cookie):
    m = jc.jobs[cookie]
    return to_json(m)

@bottle.route('/job/step/<cookie>/<n:int>/<result:re:success|failed>', method='GET')
def finish_step(cookie, n, result):
    note = None
    m = jc.finish_test_step(cookie, n, result == "success", note)
    return to_json(m)

@bottle.route('/job/abort/<cookie>/<clean>', method='GET')
def abort_test(cookie, clean=False):
    try:
        m = jc.abort_job(cookie)
    except Exception as e:
        m = e.message
    if clean:
        jc.end_job(cookie)
    return to_json(m)

@bottle.route('/firstboot/<cookie>', method='GET')
def disable_pxe_cb(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job %s" % cookie)
    # Only for cobbler
    j = jc.jobs[cookie]
    m = j.profile.cobbler_session.set_netboot_enable(j.host.get_name(), False)
    return to_json(m)


@bottle.route('/testjob/<cookie>', method='GET')
def get_bootstrap_script(cookie):
    disable_pxe_cb(cookie)

    script = None

    with open("testsuite-client.sh", "r") as f:
        script = f.read()

    r = Template(script).safe_substitute(
        igor_cookie=cookie,
        igor_current_step=jc.jobs[cookie].current_step
    )

    if not r:
        bottle.abort(404, 'No testsuite for %s' % (cookie))

    return r

@bottle.route('/job/testsuite/<name>', method='GET')
def get_testsuite_archive(name):
    t = testsuites[name]
    r = t.get_archive()
    if not r:
        bottle.abort(404, 'No testsuite for %s' % (cookie))

    return r.getvalue()



try:
    bottle.run(host='0.0.0.0', port=8080, reloader=True)
except KeyboardInterrupt:
    logger.debug("Cleaning")
    jc.clean()



