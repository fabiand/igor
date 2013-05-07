#!/bin/env python
# -*- coding: utf-8 -*-

from igor import common, log
from igor.hacks import IgordJSONEncoder
from string import Template
import argparse
import bottle
import igor.config as config
import igor.job
import igor.main
import igor.reports
import igor.utils
import importlib
import json
import os
import tarfile
import yaml


logger = log.getLogger(__name__)
logger.info("Starting igor daemon")

BOTTLE_MAX_READ_SIZE = 1024 * 1024 * 512

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", help="Config file to use",
                    default="igord.cfg")
parser.add_argument("-s", "--set", help="Override a config entry e.g. " +
                    "--set igor.backends.files/testcases/paths " +
                    "/path/to/custom/testcases",
                    action="append", nargs=2, metavar=("PATH", "VALUE"),
                    dest="updates")
ctx = parser.parse_args()

CONFIG = config.parse_config(updates=ctx.updates)

plan_backends = []
profile_backends = []
testsuite_backends = []
host_backends = []


#
# Now define our origins, where we get the items (hosts, profiles, …) from
#
plan_origins = {}
testsuite_origins = {}
profile_origins = {}
host_origins = {}

origin_priority = {}


def load_backends(hosts, profiles, testsuites, testplans):
    backendmap = [("host", host_backends, host_origins, hosts),
                  ("profile", profile_backends, profile_origins, profiles),
                  ("testsuite", testsuite_backends, testsuite_origins,
                   testsuites),
                  ("testplan", plan_backends, plan_origins, testplans)]

    for x in backendmap:
        origin_priority[x[0]] = []

    for category, dst, origin, srcs in backendmap:
        logger.info("Loading %s backends from %s" % (category, srcs))
        for modulename in srcs:
            m = importlib.import_module(modulename)
            reload(m)
            module_origins = m.initialize_origins(category, CONFIG[modulename])
            origin_priority[category].extend(x[0] for x in module_origins)
            origin.update(dict(module_origins))
            dst.append(m)
        logger.info("Origins for %s: %s" % (category, origin))
    logger.info("Priority: %s" % (origin_priority))

load_backends(CONFIG["daemon"]["enable-backends"]["hosts"],
              CONFIG["daemon"]["enable-backends"]["profiles"],
              CONFIG["daemon"]["enable-backends"]["testsuites"],
              CONFIG["daemon"]["enable-backends"]["testplans"])


#
# Now prepare the essential objects
#
jc = igor.job.JobCenter(session_path=CONFIG["daemon"]["session"]["path"],
                        hooks_path=CONFIG["daemon"]["hooks"]["path"])

inventory = igor.main.Inventory(
    plans=plan_origins,
    testsuites=testsuite_origins,
    profiles=profile_origins,
    hosts=host_origins)
inventory.check()


def to_json(obj):
    format = "json"
    root_tag = "result"

    r = json.dumps(obj, cls=IgordJSONEncoder, sort_keys=True, indent=2)

    if "format" in bottle.request.query:
        format = bottle.request.query["format"]
    if "root" in bottle.request.query:
        root_tag = bottle.request.query["root"]

    if "x-igor-format-xml" in bottle.request.headers:
        format = "xml"

    if format == "xml":
        j = json.loads(r)
        r = "<?xml-stylesheet type='text/xsl' href='/ui/index.xsl' ?>\n"
        r += igor.utils.obj2xml(root_tag, j, as_string=True)

    if format == "yaml":
        j = json.loads(r)
        r = yaml.dump_all(j)

    bottle.response.content_type = "application/%s" % format
    return r


def check_authentication(user, password):
    return user == password


#
# bottles
#

app = bottle.Bottle()


@app.route('/')
def index():
    bottle.response.content_type = "text/xml"
    return "<?xml-stylesheet type='text/xsl' href='/ui/index.xsl' ?>\n<index/>"


@app.route(common.routes.static_ui_data)
def ui_data(filename):
    return bottle.static_file(filename, root=config.DATA_DIR + "/ui/")


@app.route(common.routes.static_data)
def static_data(filename):
    return bottle.static_file(filename, root=config.DATA_DIR)


@app.route('/jobs/submit/<tname>/with/<pname>/on/<hname>')
@app.route('/jobs/submit/<tname>/with/<pname>/on/<hname>/<cookiereq>')  # FIXME
def submit_testsuite(tname, pname, hname, cookiereq=None):
    for key, name in [("testsuites", tname),
                      ("profiles", pname),
                      ("hosts", hname)]:
        item = inventory._lookup(key, name)
        if item is None:
            bottle.abort(412, "Unknown %s '%s'" % (key, name))
    xkargs = bottle.request.query.additional_kargs
    spec = igor.main.JobSpec(testsuite=inventory.testsuites()[tname],
                             profile=inventory.profiles()[pname],
                             host=inventory.hosts()[hname],
                             additional_kargs=xkargs or "")
    logger.debug("Submitting with args: %s" % str(spec))
    resp = jc.submit(spec, cookiereq)

    return to_json(resp)


@app.route(common.routes.jobs)
def get_jobs():
    return to_json(jc.get_jobs())


@app.route(common.routes.job_start)
def start_job(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    m = jc.start_job(cookie)
    return to_json(m)


@app.route(common.routes.job_status)
def job_status(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    m = jc.jobs[cookie]
    return to_json(m)


@app.route(common.routes.job_report)
def job_report(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    j = jc.jobs[cookie]
    bottle.response.content_type = "text/plain; charset=utf8"
    return str(igor.reports.job_status_to_report(j.__to_dict__()))


@app.route(common.routes.job_report_junit)
def job_report_junit(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    j = jc.jobs[cookie]
    bottle.response.content_type = "application/xml; charset=utf8"
    return str(igor.reports.job_status_to_junit(j.__to_dict__()))


@app.route(common.routes.job_step_skip)
def skip_step(cookie, n):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    m = jc.skip_step(cookie, n)
    return to_json(m)


@app.route(common.routes.job_step_finish)
def finish_step(cookie, n, result):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    m = jc.finish_test_step(cookie, n, result == "success", None)
    return to_json(m)


@app.route(common.routes.job_step_result)
def get_step(cookie, step):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    m = jc.test_step_result(cookie, step)
    return to_json(m)


@app.route(common.routes.job_step_annotate, method='PUT')
def annotate_step(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    j = jc.jobs[cookie]
    data = bottle.request.body.read(BOTTLE_MAX_READ_SIZE)
    j.annotate(data)


@app.route(common.routes.job, method='DELETE')
@app.route(common.routes.job_abort)
def abort_job(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    try:
        m = jc.abort_job(cookie)
    except Exception as e:
        m = e.message
    return to_json(m)


@app.route(common.routes.job_testsuite)
def get_job_testsuite_archive(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    t = jc.jobs[cookie].testsuite
    r = t.get_archive()
    if not r:
        bottle.abort(404, 'No testsuite for %s' % (cookie))

    return r.getvalue()


@app.route(common.routes.job_artifacts)
def list_artifact(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    j = jc.jobs[cookie]
    data = to_json(j.list_artifacts())
    return data


@app.route(common.routes.job_artifacts_archive)
def get_artifacts_archive(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    j = jc.jobs[cookie]
    bottle.response.content_type = "application/x-bzip2"
    return j.get_artifacts_archive().getvalue()


@app.route(common.routes.job_artifact, method='PUT')
def add_artifact(cookie, name):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    if "/" in name:
        bottle.abort(412, "Name may not contain slashes")
    j = jc.jobs[cookie]
    data = bottle.request.body.read(BOTTLE_MAX_READ_SIZE)
    j.add_artifact_to_current_step(name, data)


@app.route(common.routes.job_artifact)
def get_artifact(cookie, name):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    j = jc.jobs[cookie]
    bottle.response.content_type = "text/plain; charset=utf8"
    return str(j.get_artifact(name))


@app.route('/firstboot/<cookie>')
@app.route(common.routes.job_set_boot_profile)
def disable_pxe_cb(cookie, enable_pxe=False):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    j = jc.jobs[cookie]
    m = j.profile.enable_pxe(j.host, enable_pxe)
    return to_json(m)


@app.route(common.routes.job_set_kernelargs)
def set_kernelargs_cb(cookie, kernelargs):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)
    raise Exception("Not implemented yet, but needed for updates")
    j = jc.jobs[cookie]
    m = j.profile.set_kargs(j.host, kernelargs)
    return to_json(m)


@app.route(common.routes.job_bootstrap)
@app.route('/' + common.routes.job_bootstrap)
def get_bootstrap_script(cookie):
    if cookie not in jc.jobs:
        bottle.abort(404, "Unknown job '%s'" % cookie)

    disable_pxe_cb(cookie)

    script = None

    with open(os.path.join(config.DATA_DIR, "client-bootstrap.sh"), "r") as f:
        script = f.read()

    r = Template(script).safe_substitute(
        igor_cookie=cookie,
        igor_current_step=jc.jobs[cookie].current_step,
        igor_testsuite=jc.jobs[cookie].testsuite.name
    )

    if not r:
        bottle.abort(404, 'No testsuite for %s' % (cookie))

    return r


@app.route(common.routes.testsuites)
def list_testsuites():
    testsuites = inventory.testsuites()
    return to_json(testsuites)


@app.route(common.routes.testsuites_validate)
def validate_testsuites():
    testsuites = inventory.testsuites().items()
    r = {}
    for n, suite in testsuites:
        r[n] = suite.validate()
    return r


@app.route(common.routes.testsuite_summary)
def get_testsuite_summary(name):
    testsuites = inventory.testsuites()
    if name not in testsuites:
        bottle.abort(404, "Unknown testsuite '%s'" % name)
    return to_json(testsuites[name])


@app.route(common.routes.testsuite_archive)
@app.route(common.routes.testsuite_archive + '/<tarball>')
def get_testsuite_archive(name, tarball="testsuite.tar"):
    testsuites = inventory.testsuites()
    if name not in testsuites:
        bottle.abort(404, "Unknown testsuite '%s'" % name)
    t = testsuites[name]
    r = t.get_archive()
    if not r:
        bottle.abort(404, 'No testsuite for %s' % (name))
    bottle.response.content_type = "application/x-tar; charset=binary"
    return r.getvalue()


@app.route(common.routes.testplans)
def list_plans():
    return to_json(inventory.plans())


@app.route(common.routes.testplan)
def plan_info(name):
    if name not in inventory.plans():
        bottle.abort(404, "Unknown plan: %s" % name)
    plan = inventory.plans()[name]
    return to_json(plan)


@app.route(common.routes.testplan_start)
def run_plans(name):
    if name not in inventory.plans():
        bottle.abort(404, "Unknown plan: %s" % name)
    plan = inventory.plans()[name]
    plan.inventory = inventory      # FIXME not very nice
    plan.variables.update({k: bottle.request.query[k]
                           for k in bottle.request.query.keys()})
    worker = jc.submit_plan(plan)
    return to_json(worker.__to_dict__())


@app.route(common.routes.testplan)
def testplan_summary(name):
    if name not in inventory.plans():
        bottle.abort(404, "Unknown plan: %s" % name)
    return to_json(inventory.plans()[name])


@app.route(common.routes.testplan_status)
def status_plans(name):
    if name not in inventory.plans():
        bottle.abort(404, "Unknown plan: %s" % name)
    r = jc.status_plan(name)
    return to_json(r)


@app.route(common.routes.testplan_report)
def testplan_report(name):
    if name not in inventory.plans():
        bottle.abort(404, "Unknown plan: %s" % name)
    r = jc.status_plan(name)
    bottle.response.content_type = "text/plain; charset=utf8"
    return str(igor.reports.testplan_status_to_report(r))


@app.route(common.routes.testplan_report_junit)
def testplan_junit_report(name):
    if name not in inventory.plans():
        bottle.abort(404, "Unknown plan: %s" % name)
    r = jc.status_plan(name)
    bottle.response.content_type = "application/xml; charset=utf8"
    xml = igor.reports.testplan_status_to_junit_report(r)
    return igor.reports.to_xml_str(xml)


@app.route(common.routes.testplan_abort)
def abort_plans(name):
    if name not in inventory.plans():
        bottle.abort(404, "Unknown plan: %s" % name)
    r = jc.abort_plan(name)
    return to_json(r.__to_dict__())


@app.route(common.routes.profiles)
def list_profiles():
    return to_json(inventory.profiles())


@app.route(common.routes.hosts)
def list_hosts():
    return to_json(inventory.hosts())


@app.route(common.routes.testcase_source)
def testcase_source(suitename, setname, casename):
    testsuites = inventory.testsuites()
    if suitename not in testsuites:
        bottle.abort(404, "Unknown testsuite '%s'" % suitename)
    suite = testsuites[suitename]
    tset = None
    for _tset in suite.testsets:
        if _tset.name == setname:
            tset = _tset
    if tset is None:
        bottle.abort(404, "Unknown testset '%s'" % setname)
    case = None
    for _case in tset.testcases():
        if _case.name == casename:
            case = _case
    if case is None:
        bottle.abort(404, "Unknown testcase '%s'" % casename)
    source = case.source()
    if source is None:
        bottle.abort(404, "No source '%s'" % casename)
    else:
        bottle.response.content_type = "text/plain"
    return source


@app.route(common.routes.profile, method='PUT')
def profile_from_vmlinuz_put(pname):
    reqfiles = set(["kernel", "initrd", "kargs"])
    _tmpdir = igor.utils.TemporaryDirectory()
    with _tmpdir as tmpdir:
        logger.debug("Using PUT tmpdir %s" % tmpdir)
        with tarfile.open(fileobj=bottle.request.body) as tarball:
            arcfiles = tarball.getnames()
            logger.debug("PUT %s" % arcfiles)
            for arcfile in arcfiles:
                assert os.path.basename(arcfile) == arcfile, \
                    "not paths allowed"
            tarball.extractall(path=tmpdir)
        written_files = {}
        for rf in reqfiles:
            fn = rf
            header = "x-%s-filename" % rf
            if header in bottle.request.headers:
                fn = bottle.request.headers[header]
            _tmpdir.cleanfile(fn)
            written_files[rf] = os.path.join(tmpdir, os.path.basename(fn))
        print written_files
        if not all([r in written_files.keys() for r in reqfiles]):
            bottle.abort(412, "Expecting %s files" % str(reqfiles))

        origin_to_use = origin_priority["profile"][0]
        inventory.create_profile(oname=origin_to_use,
                                 pname=pname,
                                 **written_files)
    _tmpdir.clean()


@app.route(common.routes.profile_set_kernelargs, method='GET')
@app.route(common.routes.profile_set_kernelargs, method='POST')
def profile_kargs(pname):
    if pname not in inventory.profiles():
        bottle.abort(404, "Unknown profile")
    kargs = bottle.request.forms.kargs
    n_kargs = "NO_KARGS_FOUND"
    if kargs:
        if "{igor_cookie}" not in kargs:
            bottle.abort(412, "{igor_cookie} not found in kargs, this is " +
                              "needed to initiate the callback to Igor, " +
                              "e.g. boot_trigger=igor/testjob/{igor_cookie}")
        n_kargs = inventory.profiles()[pname].kargs(kargs)
    else:
#        bottle.abort(412, "No kargs specified")
        n_kargs = inventory.profiles()[pname].kargs()
    return n_kargs


@app.route(common.routes.profile, method='DELETE')
@app.route(common.routes.profile_delete)
def delete_profile(pname):
    if pname not in inventory.profiles():
        bottle.abort(404, "Unknown profile")
    try:
        inventory.profiles()[pname].delete()
    except Exception as e:
        # FIXME could be solved in the cobblre backend
        logger.warning("An error occurred while removing a " +
                       "profile: %s (%s)" % (e.message, e))


@app.route(common.routes.server_log)
def get_log():
    bottle.response.content_type = "text/plain; charset=utf8"
    return igor.log.backlog()

if __name__ == "__main__":
    try:
    #    logger.info("Starting igord")
        bottle.run(app, host='0.0.0.0', port=8080, reloader=False)
    except KeyboardInterrupt:
        logger.debug("Ending igor")
