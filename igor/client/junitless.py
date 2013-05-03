#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# builder.py - Copyright (C) 2012 Red Hat, Inc.
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

# http://www.darkcoding.net/software/pretty-command-line-console-output-on-\
# unix-in-python-and-go-lang/
# http://bergie.iki.fi/files/nexus10-shell.png
# https://github.com/gruntjs/grunt/blob/master/lib/grunt/log.js
# http://superuser.com/questions/270214/how-can-i-change-the-colors-of-my-\
# xterm-using-ansi-escape-sequences

from lxml import etree
import sys
import datetime
import re
import fabulous.color as c


def clearscreen():
    print('\033[H\033[2J')


class ansi(unicode):
    def __init__(self, txt, with_markup=True):
        self.txt = txt
        self.with_markup = with_markup

    @property
    def plain(self):
        return ansi(c.plain(self.txt))

    @property
    def bold(self):
        return ansi(c.bold(self.txt))

    @property
    def italic(self):
        return ansi(c.italic(self.txt))

    @property
    def underline(self):
        return ansi(c.underline(self.txt))

    @property
    def inverse(self):
        return ansi(c.flip(self.txt))

    @property
    def markup(self):
        txt = self.txt
        # Make _foo_ underline.
        underline_pat = "(\s|^)_(\S|\S[\s\S]+?\S)_(?=[\s,.!?]|$)"
        txt = re.sub(underline_pat,
                     lambda m: m.groups()[0] + ansi(m.groups()[1]).underline,
                     txt)
        # Make *foo* bold.
        bold_pat = "(\s|^)\*(\S|\S[\s\S]+?\S)\*(?=[\s,.!?]|$)"
        txt = re.sub(bold_pat,
                     lambda m: m.groups()[0] + ansi(m.groups()[1]).bold,
                     txt)
        return ansi(txt)

    @property
    def black(self):
        return ansi(c.black(self.txt))

    @property
    def red(self):
        return ansi(c.red(self.txt))

    @property
    def green(self):
        return ansi(c.green(self.txt))

    @property
    def yellow(self):
        return ansi(c.yellow(self.txt))

    @property
    def blue(self):
        return ansi(c.blue(self.txt))

    @property
    def magenta(self):
        return ansi(c.magenta(self.txt))

    @property
    def cyan(self):
        return ansi(c.cyan(self.txt))

    @property
    def white(self):
        return ansi(c.white(self.txt))


class Log(object):
    fail_errorcount = 0
    _indent = 0

    def write(self, msg):
        prefix = " " * self._indent
        lines = msg.split("\n")
        msg = "\n".join("%s%s" % (prefix, line)
                        for line in lines)
        print("%s%s" % (" " * self._indent, msg))

    def writeln(self, msg):
        self.write(msg)

    def indented(self, size=1):
        parent = self

        class IndentedLog(Log):
            def __enter__(self):
                parent._indent += size

            def __exit__(self, exc_type, exc_value, traceback):
                parent._indent -= size

        return IndentedLog()

    def _indented(self, msg):
        return ansi('>> %s' % msg.replace("\n", "\n>> "))

    def warn(self, msg=None):
        if msg:
            self.writeln(self._indented(msg).red)
        else:
            self.writeln(ansi("ERROR").red)

    def error(self, msg):
        self.fail_errorcount += 1
        self.warn(msg)

    def ok(self, msg=None):
        if msg:
            self.writeln(self._indented(msg).green)
        else:
            self.writeln(ansi("OK").green)

    def success(self, msg):
        self.writeln(ansi(msg).green)

    def fail(self, msg):
        self.writeln(ansi(msg).red)

    def header(self, msg):
        self.writeln(ansi(msg).underline)

    def subhead(self, msg):
        self.writeln(ansi(msg).bold)

    def debug(self, msg):
        self.writeln('[D] %s' % ansi(msg).magenta)

if False:
    print(ansi("foo").green.bold)
    print(ansi("_underline_ and *bold*").markup)

    log = Log()

    log.warn("Argh!")
    log.error("an error")
    log.ok("it's ok")
    log.success("yeah we did it!")
    log.fail("darn, it failed")
    log.header("Heads up!")
    log.subhead("Quick")
    log.debug("Details ...")

    #print ansi.all_colors()


class LogBuilder(object):
    _last_testset = None
    log = None

    def __init__(self, log=None):
        self.log = log or Log()

    def from_file(self, filename):
        tree = etree.parse(filename)
        root = tree.getroot()
        return self.build(root)

    def from_txt(self, txt):
        root = etree.XML(txt)
        return self.build(root)

    def from_xml(self, xml):
        return self.build(xml)

    def build(self, node):
        builder_for_node = {
            "testsuites": self._build_testsuites,
            "testsuite": self._build_testsuite,
            "testcase": self._build_testcase,
        }

        assert node.tag in builder_for_node

        builder = builder_for_node[node.tag]

        return builder(node)

    def _build_testsuites(self, node):
        with self.log.indented():
            for testsuite in node.iter("testsuite"):
                self.build(testsuite)

    def _build_testsuite(self, node):
        self.log.header("\n%s" % node.attrib["name"].capitalize())

        props = {e.attrib["name"]: e.attrib["value"]
                 for e in node.findall("properties/property")}
        self.log.writeln(u"Session:  %s" % node.attrib["id"])
        self.log.writeln(u"Host:     %s" % props["host"])
        self.log.writeln(u"Profile:  %s" % props["profile"])
        self.log.writeln(u"Cmdline 𝚫: %s" % props["additional_kargs"])

        with self.log.indented():
            for testcase in node.iter("testcase"):
                self.build(testcase)

        attrs = {"Time": "%.2fs" % float(node.attrib["time"]),
                 "Tests": "%s" % node.attrib["tests"],
                 "Failures": "%s" % node.attrib["failures"]
                 }

        self.log.writeln("")
        txt = ", ".join("%s: %s" % (f, v) for f, v in attrs.items())
        if int(node.attrib["failures"]):
            self.log.error(txt)
        else:
            self.log.ok(txt)

        #in %.2fs
        self.log.writeln(ansi("\nLast update: %s" %
                              datetime.datetime.today()).cyan)

    def _build_testcase(self, node):
        is_failure = node.findall("failure")
        is_skipped = "skipped" in node.attrib
        is_running = "running" in node.attrib
        is_queued = "queued" in node.attrib
        is_notrun = "notrun" in node.attrib
        is_aborted = "aborted" in node.attrib

        def sanitize_name(name):
            name = name.replace("_", " ")
            name = re.sub("\.\w+$", "", name)
            if "-" in name:
                idx, name = name.split("-", 1)
                name = "%2s. %s" % (idx, name.capitalize())
            else:
                name = name.capitalize()
            return name
        # ⏲   ✓ ☀ ⛖ ⛗   ✗ ⛔ ⛈ ☁   ⛅

        testset = node.attrib["part-of-testset"]
        if testset != self._last_testset:
            testsetname = sanitize_name(testset)
            self.log.subhead("\n%s" % testsetname)
            self._last_testset = testset

        _fmt = ansi(" {name}{time}")
        if is_aborted:
            fmt = ansi(u"⛔" + _fmt).white
        elif is_failure:
            fmt = ansi(u"⛈" + _fmt).red
        elif is_running:
            fmt = ansi(u"⏲" + _fmt).magenta
        elif is_skipped:
            fmt = ansi(u"⏩" + _fmt).yellow
        elif is_queued or is_notrun:
            fmt = ansi(u"◌").white + _fmt
        else:
            fmt = ansi(u"☀").green + _fmt

        name = sanitize_name(node.attrib["name"])
        time = " (%.2fs)" % float(node.attrib["time"]) \
            if node.attrib["time"] else ""
        self.log.write(fmt.format(name=name, time=time))


if __name__ == "__main__":
    junitfile = sys.argv[1]

    def pp(tree):
        print(etree.tostring(tree, pretty_print=True))

    #tree = etree.parse(junitfile)
    #root = tree.getroot()
    #pp(tree)

    builder = LogBuilder()
    builder.from_file(junitfile)
