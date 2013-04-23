#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# igorc - Copyright (C) 2013 Red Hat, Inc.
# Written by Fabian Deutsch <fabiand@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.


class routes(object):
    static_ui_data = '/ui/<filename>'
    static_data = '/static/data/<filename>'

    testsuite_submit = '/jobs/submit/<tname>/with/<pname>/on/<hname>'

    jobs = '/jobs'
    job = '/jobs/<cookie>'
    job_start = '/jobs/<cookie>/start'
    job_abort = '/jobs/<cookie>/abort'
    job_status = '/jobs/<cookie>/status'
    job_report = '/jobs/<cookie>/report'
    job_testsuite = '/jobs/<cookie>/testsuite'
    job_artifacts = '/jobs/<cookie>/artifacts'
    job_artifacts_archive = '/jobs/<cookie>/archive' # FIXME
    job_artifact = '/jobs/<cookie>/artifacts/<name>'

    job_step_skip = '/jobs/<cookie>/step/<n:int>/skip'
    job_step_finish = '/jobs/<cookie>/step/<n:int>/<result:re:success|failed>'
    job_step_result = '/jobs/<cookie>/step/<n:int>/result'
    job_step_annotate = '/jobs/<cookie>/step/current/annotate'

    job_set_boot_profile = '/jobs/<cookie>/set/enable_pxe/<enable_pxe>'
    job_set_kernelargs = '/jobs/<cookie>/set/kernelargs/<kernelargs>'

    job_bootstrap = '/testjob/<cookie>'

    testsuites = '/testsuites'
    testsuites_validate = '/testsuites/validate'
    testsuite_summary = '/testsuites/<name>/summary'
    testsuite_archive = '/testsuites/<name>/download'

    testplans = '/testplans'
    testplan = '/testplans/<name>'
    testplan_start = '/testplans/<name>/submit'
    testplan_abort = '/testplans/<name>/abort'
    testplan_status = '/testplans/<name>/status'
    testplan_report = '/testplans/<name>/report'
    testplan_report_junit = '/testplans/<name>/report/junit'
    testplan_summary = ''

    profiles = '/profiles'
    profile = '/profiles/<pname>'
    profile_delete = '/profiles/<pname>/remove'
    profile_set_kernelargs = '/profiles/<pname>/kargs'

    hosts = '/hosts'

    testcase_source = '/testcases/<suitename>/<setname>/<casename>/source'

    server_log = '/server/log'