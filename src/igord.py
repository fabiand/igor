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
import example

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class StatemachineEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Job) or isinstance(obj, Testsuite) or \
           isinstance(obj, Testset) or isinstance(obj, Testcase):
            return obj.__json__()
        return json.JSONEncoder.default(self, obj)

def to_json(obj):
    bottle.response.content_type = "application/json"
    return json.dumps(obj, cls=StatemachineEncoder, sort_keys=True, indent=2)


jc = JobCenter()


@bottle.route('/jobs', method='GET')
def get_jobs():
    return to_json(jc.get_jobs())

@bottle.route('/job/submit/<testsuite>/with/<profile>/on/<host>', method='GET')
def submit_testsuite(testsuite, profile, host):
    resp = jc.submit_testsuite(example.testsuite, example.profile, example.host)
    return to_json(resp)

@bottle.route('/job/next', method='GET')
def run_next_job():
    m = jc.run_next_job()
    return to_json(m)

@bottle.route('/job/current', method='GET')
def current_job():
    m = jc.current_job
    return to_json(m)

def _req_cookie():
    cookie_key = "x-igor-cookie"
    if cookie_key not in bottle.request.headers:
        bottle.abort("Cookie missing")
    cookie = bottle.request.headers[cookie_keys]
    if cookie not in jc.open_jobs:
        bottle.abort("Unknown job")
    return cookie

@bottle.route('/test/step/<n>/<note>', method='GET')
def finish_step(n, note=None):
    cookie = _req_cookie()
    m = jc.finish_test_step(cookie, n, note)
    return to_json(m)

@bottle.route('/test/abort', method='GET')
def abort_test(n, note=None):
    cookie = _req_cookie()
    m = jc.abort_test(cookie)
    return to_json(m)

@bottle.route('/firstboot/<cookie>', method='GET')
def disable_pxe_cb(cookie):
    if cookie not in jc.open_jobs:
        bottle.abort("Unknown firstboot job")
    # Only for cobbler
    j = jc.open_jobs[cookie]
    m = j.profile.session.set_netboot_enable(j.host.get_name(), False)
    return to_json(m)


@bottle.route('/testsuite/<cookie>', method='GET')
def get_testsuite(cookie):
#    r = read_file(session, filename)
    r = Template("""
#/bin/bash

SESSION=${cookie}
KERNELARG=$(egrep -o 'testsuite=[^[:space:]]+' /proc/cmdline)
BASEURL=${KERNELARG#testsuite=}
BASEURL=${BASEURL%/testsuite/$SESSION}

echo $KERNELARG $BASEURL

put_file()
{
    DST=$1
    FILENAME=$2
    curl --silent \
        --request PUT \
        --header "X-Igord-Session: $SESSION" \
        --header "X-Igord-Filename: $DST" \
        --upload-file "$FILENAME" \
        "$BASEURL/documents"
}

echo Hello Node.

put_file passwd /etc/passwd

sleep 3

exit 0
""").safe_substitute(cookie=cookie)

    if not r:
        bottle.abort(404, 'No testsuite for %s' % (cookie))
    return r

bottle.run(host='0.0.0.0', port=8080, reloader=True)

