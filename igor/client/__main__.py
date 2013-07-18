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

from igor import log
from igor.client import junitless, event
from igor.client.main import IgordAPI
from lxml import etree
import argparse
import cmd
import logging
import os
import shlex
import subprocess
import urlparse


def prettyxml(xmltree):
    return etree.tostring(xmltree, pretty_print=True)


class Context(object):
    def __init__(self):
        self.remote = "127.0.0.1"
        self.port = "8080"
        self.event_port = "6379"
        self.session = ""
        self.notify = False


class IgorClient(cmd.Cmd):
    intro = "Welcome to igorc, the interactive connection ot igord.\n"
    prompt = "igorc> "

    ctx = Context

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.ctx = Context()
        self._logger = logging.getLogger(__name__)

    @property
    def logger(self):
        return self._logger

    def default(self, line):
        if line == "EOF":
            return True
        return cmd.Cmd.default(self, line)

    def emptyline(self):
        print("Enter ? or ?<cmd> for help")

    def do_quit(self, args):
        """quit
        Quit igorc
        """
        return True

    def do_env(self, args):
        """env
        Get environment variables
        """
        env = self.ctx.__dict__
        print("\n".join("%s: %s" % i for i in env.items()))
        print("(%d variables)" % len(env))

    def _parse_do_args(self, prog, line, arguments):
        parser = argparse.ArgumentParser(prog=prog)
        for args, kwargs in arguments:
            args = (args,) if type(args) in [str, unicode] else args
            parser.add_argument(*args, **kwargs)
        return parser.parse_args(shlex.split(line))

    def do_set(self, line):
        """set <key> [<value>]
        Set environment variables
        """
        pargs = [("key", {}),
                 ("value", {"nargs": "?"})]
        _args = self._parse_do_args("set", line, pargs)
        if _args.value:
            self.ctx.__dict__[_args.key] = _args.value

    def __igorapi(self):
        remote = self.ctx.remote
        port = self.ctx.port
        return IgordAPI(remote, port)

    def do_jobs(self, args):
        """jobs
        List all available jobs
        """
        igor = self.__igorapi()
        print(prettyxml(igor.jobs()))

    def do_profiles(self, args):
        """profiles
        List all available profiles
        """
        igor = self.__igorapi()
        print(prettyxml(igor.profiles()))

    def do_hosts(self, args):
        """hosts
        List all available hosts
        """
        igor = self.__igorapi()
        print(prettyxml(igor.hosts()))

    def do_testsuites(self, args):
        """testsuites
        List all available testsuites
        """
        igor = self.__igorapi()
        print(prettyxml(igor.testsuites()))

    def do_testplans(self, args):
        """testplans
        List all available testplans
        """
        igor = self.__igorapi()
        print(prettyxml(igor.testplans()))

    def do_profile_new_from_livecd(self, line):
        """profile_from_livecd <profilename> <isoname> [<additional_kargs>]
        """
        pargs = [("profilename", {}),
                 ("isoname", {}),
                 ("additional_kargs", {"nargs": "?"})]
        _args = self._parse_do_args("profile_from_livecd", line, pargs)
        profile = self.__igorapi().profile(_args.profilename)
        profile.new_from_livecd(_args.isoname, _args.additional_kargs)

    def do_profile_remove(self, line):
        """profile_remove <profilename>
        """
        pargs = [("profilename", {})]
        _args = self._parse_do_args("profile_remove", line, pargs)
        profile = self.__igorapi().profile(_args.profilename)
        print(profile.delete())

    def do_testplan_start(self, line):
        """testplan_start <testplanname> [<substitutions>]
        substitutions: k0=v0,k1=v1,...
        """
        pargs = [("testplanname", {}),
                 ("substitutions", {"nargs": "*", "metavar": "KEY=VALUE"})]
        _args = self._parse_do_args("testplan_start", line, pargs)
        _substitutions = dict([tuple(pair.split("=", 1))
                               for pair in _args.substitutions])
        testplan = self.__igorapi().testplan(_args.testplanname)
        testplan.start(_substitutions)

    def do_testplan_abort(self, line):
        """testplan_abort <testplanname>
        """
        pargs = [("testplanname", {})]
        _args = self._parse_do_args("testplan_abort", line, pargs)
        testplan = self.__igorapi().testplan(_args.testplanname)
        testplan.abort()

    def do_testplan_on_iso(self, line):
        """testplan_on_iso <testplan> <isoname> [<additional_kargs>]
                           [-s <substitutions>]
        """
        pargs = [("testplanname", {}),
                 ("isoname", {}),
                 ("additional_kargs", {"nargs": "?", "default": ""}),
                 ("-s", {"dest": "substitutions",
                         "metavar": "substitutions",
                         "help": "Variables to be replaced in the testplan" +
                         ". {varname} can be used in the testplan."})]
        _args = self._parse_do_args("testplan_on_iso", line, pargs)
        igor = self.__igorapi()

        profilename = os.path.basename(_args.isoname)

        substitutions = {"tbd_profile": profilename}
        if _args.substitutions:
            parsed_substs = dict(pair.split("=", 1) for pair in
                                 _args.substitutions.split(","))
            substitutions.update(parsed_substs)
        print substitutions
        profile = igor.profile(profilename)
        profile.new_from_livecd(_args.isoname, _args.additional_kargs)
        testplan = igor.testplan(_args.testplanname)
        testplan.start(substitutions=substitutions)
        self.do_watch_testplan(_args.testplanname)
        profile.delete()

    def do_watch_job(self, line):
        """watch_job [<sessionid>]
        Watch a running job
        """
        pargs = [("sessionid", {"nargs": "?", "default": self.ctx.session})]
        _args = self._parse_do_args("watch_job", line, pargs)

        job = self.__igorapi().job(_args.sessionid)

        def job_reportxml_cb(updated_sessiondid):
            if updated_sessiondid == _args.sessionid:
                # Only update screen if "our" job changed
                return job.report_junit()
            return None

        self.watch_events(job_reportxml_cb)

    def do_watch_testplan(self, line):
        """watch_testplan <testplanname>
        Watch a running testplan
        """
        pargs = [("testplanname", {"nargs": "?", "default": self.ctx.session})]
        _args = self._parse_do_args("watch_testplan", line, pargs)

        testplan = self.__igorapi().testplan(_args.testplanname)

        def job_reportxml_cb(updated_sessiondid):
            return testplan.report_junit()

        self.watch_events(job_reportxml_cb)

    def watch_events(self, reportxml_cb):
        remote = self.ctx.remote
        event_port = self.ctx.event_port

        builder = junitless.LogBuilder()

        def parse_state(reportxml):
            gp = lambda p: reportxml.xpath("//property[@name='%s']/@value" % p)
            states = gp("status")
            is_endstates = gp("is_endstate")
            is_endstate = all(n == "True" for n in is_endstates)
            return states, is_endstate

        try:
            reportxml = reportxml_cb(None)
            junitless.clearscreen()
            builder.from_xml(reportxml)

            builder.log.writeln("Waiting for event ...")
            for ev in event.follow_events(remote, event_port):
                reportxml = reportxml_cb(ev["session"])

                if reportxml is not None:
                    states, is_endstate = parse_state(reportxml)

                    junitless.clearscreen()
                    builder.from_xml(reportxml)

                    if is_endstate:
                        self.logger.debug("State: %s" % states)
                        self.logger.debug("Found endstate, stop watching")
                        break

                    builder.log.writeln("Waiting ...")
                    builder.log.writeln("(Press Ctrl+C to stop watching)")

        except KeyboardInterrupt:
            self.logger.debug("event watcher got interrupted.")

    def do_firewall_open(self, args):
        """firewall_open
        Open relevant ports
        """
        ports = [self.ctx.port, self.ctx.event_port]
        self.logger.debug("About to open the relevant TCP ports: %s" % ports)
        for port in ports:
            print("Opening %s/tcp" % port)
            print(subprocess.check_output(["sudo", "firewall-cmd",
                                           "--add-port=%s/tcp" % port]))


class Notify(object):
    def notify(self, summary, body="", urgency="low", icon=None,
               expiretime=2000):
        cmd = ["notify-send",
               "--expire-time", expiretime,
               "--urgency", urgency,
               "--summary", summary
               ]
        if icon:
            cmd += ["--icon", icon]
        if body:
            cmd += ["--body", body]
        subprocess.check_call(cmd)

    def ok(self, summary, body=None):
        self.notify(summary, body, "low", "weather-clear")

    def failure(self, summary, body=None):
        self.notify(summary, body, "urgent", "weather-showers")


if __name__ == "__main__":
    # Parse args
    parser = argparse.ArgumentParser(prog="igorc",
                                     description="Communicate with igord")
    parser.add_argument("-c", "--connect", metavar="URI",
                        help="URL of the igor server. Default: localhost:8080",
                        default="http://127.0.0.1:8080")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print informational messages")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Print debug messages")
    parser.add_argument("-n", "--notify",
                        action="store_true",
                        help="Enable desktop notifications using libnotify")
    parser.add_argument("command", metavar="CMD", nargs="*",
                        help="Run this command(s) and quit")
    namespace = parser.parse_args()
    url = urlparse.urlparse(namespace.connect)

    # Configure logging
    log.configure("/tmp/igorc.log")
    lvl = logging.INFO if namespace.verbose else logging.WARNING
    lvl = logging.DEBUG if namespace.debug else lvl
    logging.basicConfig(level=lvl)

    # Setup client
    client = IgorClient()
    client.ctx.remote = url.hostname
    client.ctx.port = url.port
    client.ctx.notify = namespace.notify

    if namespace.command:
        for command in namespace.command:
            if command.strip():
                print("<!-- Running:\n %s -->" % command)
                client.onecmd(command)
    else:
        client.cmdloop()
