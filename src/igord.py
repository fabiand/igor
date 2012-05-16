#!/bin/env python

import json
import bottle
from bottle import route, run, request, abort
import os
import base64
from string import Template
import uuid, time
import logging

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

from statemachine import *
a_testsuite = Testsuite([
    Testset([ "case_a", "case_b", "case_c" ]),
    Testset([ "case_d", "case_e", Testcase(filename="case_f") ])
])

#class JobCenter(object):

def to_json(obj):
    return json.dumps(obj, cls=StatemachineEncoder, sort_keys=True, indent=2)

open_jobs = {}
closed_jobs = []

@route('/jobs', method='GET')
def get_jobs():
    return to_json({
        "open": open_jobs,
        "closed": closed_jobs
        })


@route('/test/<testsuite>/on/<build>', method='GET')
def submit_test(testsuite, build):
    cookie = "%s-%d" % (time.strftime("%Y%m%d"), len(open_jobs)+len(closed_jobs))

    j = Job(a_testsuite)
    j.created_at = time.time()
    j.cookie = cookie
    open_jobs[cookie] = j

    logger.debug("Created job %s" % repr(j))

    return to_json({"cookie": cookie})

@route('/abort/<cookie>', method='GET')
def abort_test(cookie):
    logger.debug("Aborting %s" % cookie)
    if cookie in open_jobs:
        j = open_jobs[cookie]
        j.abort()
        closed_jobs.append(j)
        del open_jobs[cookie]
        logger.debug("Aborted %s", repr(j))

@route('/session/<cookie>/finish_step/<step>/<is_success>', method='GET')
def finish_test_step(cookie, step, is_success):
    j = open_jobs[cookie]
    j.finish_step(step, is_success)

    return to_json(j)

@route('/testsuite/<cookie>', method='GET')
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
        abort(404, 'No testsuite for %s' % (cookie))
    return r

#j = JobCenter()

run(host='0.0.0.0', port=8080, reloader=True)

