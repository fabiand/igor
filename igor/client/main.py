# -*- coding: utf-8 -*-
#
# Copyright (C) 2013  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Fabian Deutsch <fabiand@fedoraproject.org>
#
from igor.common import routes
from lxml import etree
import io
import logging
import os
import re
import subprocess
import tarfile
import tempfile
import time
import urllib
import urllib2


def check_isfile(filename):
    if not os.path.isfile(filename):
        raise RuntimeError("File '%s' does not exist." % filename)


class HTTPHelper(object):
    logger = None

    def __init__(self):
        self.logger = logging.getLogger(self.__module__)

    def request(self, url, method="GET", data=None, headers={}):
        """Request a page from a URL

        Args:
            url: URL to request page from

        Return:
            Returns the page contents as a str
        """
        reply = None
        self.logger.debug("Requesting %s: %s" % (method, url))
        if method in ["PUT", "DELETE"]:
            opener = urllib2.build_opener(urllib2.HTTPHandler)
            request = urllib2.Request(url, data=data, headers=headers)
            request.get_method = lambda: method
            reply = opener.open(request)
        else:
            reply = urllib2.urlopen(url).read()
        return reply

    def put(self, url, data, headers={}):
        self.request(url, "PUT", data, headers)

    def put_binary(self, url, data, headers={}):
        return self.put(url, data,
                        {'Content-Type': 'application/octet-stream'})

    def delete(self, url):
        self.request(url, "DELETE")


class IgordAPI(object):
    """An interface to the basic REST-API of igor
    """
    _http = None
    _logger = None
    host = None
    port = None

    def __init__(self, host="127.0.0.1", port=8080):
        self.host = host
        self.port = port
        self._http = HTTPHelper()
        self._logger = logging.getLogger(self.__module__)

    @property
    def logger(self):
        return self._logger

    def url(self, route="/", query={}, **route_args):
        """Returns the URL of the remote Igord server with the given route
        """
        _route = route
        if route_args:
            _route = re.sub("<([^>:]*)(:[^>]*)?>", "{\\1}", _route)
            _route = _route.format(**route_args)
        _query = "?" + urllib.urlencode(query.items()) if query else ""
        if "<" in _route:
            self.logger.debug("Route: %s" % route)
            self.logger.debug("RouteArgs: %s" % route_args)
            self.logger.debug("Query: %s" % query)
            self.logger.debug("New Route: %s" % _route)
            self.logger.debug("New Query: %s" % _query)
            raise RuntimeError("Some placeholders weren't filled in route.")
        return "http://{host}:{port}{route}{query}".format(host=self.host,
                                                           port=self.port,
                                                           route=_route,
                                                           query=_query)

    def route_request(self, route, **route_args):
        """Request a route and return an XML tree
        """
        url = self.url(route, {"format": "xml"}, **route_args)
        pagedata = self._http.request(url)
        tree = etree.XML(pagedata) if pagedata else None
        return tree

    def jobs(self):
        return self.route_request(routes.jobs)

    def testsuites(self):
        return self.route_request(routes.testsuites)

    def hosts(self):
        return self.route_request(routes.hosts)

    def profiles(self):
        return self.route_request(routes.profiles)

    def testplans(self):
        return self.route_request(routes.testplans)

    def testsuite(self, name):
        return TestsuiteAPI(self.host, self.port, name)

    def job(self, sessionid):
        return JobAPI(self.host, self.port, sessionid)

    def profile(self, name):
        return ProfileAPI(self.host, self.port, name)

    def testplan(self, name):
        return TestplanAPI(self.host, self.port, name)

    def datastore(self):
        return DatastoreAPI(self.host, self.port)


class DatastoreAPI(IgordAPI):
    def list(self):
        return self.route_request(routes.datastore)

    def upload(self, filename, data=None):
        url = self.url(routes.datastore_file, filename=filename)
        return self._http.put_binary(url, io.BytesIO(data).getvalue())

    def download(self, filename):
        url = self.url(routes.datastore_file, filename=filename)
        return self._http.request(url)

    def delete(self, filename):
        return self._http.delete(self.url(routes.datastore_file, filename=filename))


class JobAPI(IgordAPI):
    """An interface to the job related REST-API
    """
    def __init__(self, host, port, sessionid):
        super(JobAPI, self).__init__(host, port)
        self.sessionid = sessionid

    def start(self):
        return self.route_request(routes.job_start, cookie=self.sessionid)

    def abort(self):
        return self.route_request(routes.job_abort, cookie=self.sessionid)

    def status(self):
        return self.route_request(routes.job_status, cookie=self.sessionid)

    def report(self):
        url = self.url(routes.job_report, cookie=self.sessionid)
        return self.request(url)

    def report_junit(self):
        return self.route_request(routes.job_report_junit,
                                  cookie=self.sessionid)

    def artifacts(self):
        return self.route_request(routes.job_artifacts, cookie=self.sessionid)

    def step_skip(self, n):
        return self.route_request(routes.job_step_skip, cookie=self.sessionid,
                                  n=n)

    def step_finish(self, n, result="success"):
        return self.route_request(routes.job_step_finish,
                                  cookie=self.sessionid,
                                  n=n, result=result)

    def step_result(self, n):
        return self.route_request(routes.job_step_result,
                                  cookie=self.sessionid, n=n)

    def step_annotate(self, n):
        raise NotImplementedError("Needs to use PUT")
        return self.route_request(routes.job_step_annotate,
                                  cookie=self.sessionid, n=n)


class TestsuiteAPI(IgordAPI):
    """An (dummy) interface to the testsuite related REST-API
    """
    def __init__(self, host, port, name):
        super(TestsuiteAPI, self).__init__(host, port)
        self.name = name


class ProfileAPI(IgordAPI):
    """An interface to the profile related REST-API
    """
    def __init__(self, host, port, name):
        super(ProfileAPI, self).__init__(host, port)
        self.name = name

    def new(self, vmlinuz_file, initrd_file, kargs):
        filemap = {"kernel": vmlinuz_file,
                   "initrd": initrd_file,
                   "kargs": io.BytesIO(kargs)}
        headers = {"x-kernel-filename": "kernel",
                   "x-initrd-filename": "initrd",
                   "x-kargs-filename": "kargs"}

        # Create a temporary file which is used to create a tarball
        # Now add kernel+initrd+kargs file into this archive
        # And upload it via PUT
        with tempfile.NamedTemporaryFile() as tmpfile:
            self.logger.debug("Temporary archive for profile upload: %s" %
                              tmpfile.name)
            with tarfile.open(fileobj=tmpfile, mode="w") as archive:
                self.logger.debug("Adding files: %s" % filemap)
                for arcname, filename in filemap.items():
                    self.logger.debug("Adding %s" % filename)
                    if type(filename) is io.BytesIO:
                        srcobj = filename
                    else:
                        with open(filename) as fssrc:
                            srcobj = io.BytesIO(fssrc.read())
                    info = tarfile.TarInfo(name=arcname)
                    info.size = len(srcobj.getvalue())
                    info.mtime = time.time()
                    archive.addfile(tarinfo=info, fileobj=srcobj)
            tmpfile.flush()
            self.logger.debug("Archive contents: \n%s" %
                              subprocess.check_output(["tar", "tvf",
                                                       tmpfile.name]))

            tmpfile.seek(0)
            data = io.BytesIO(tmpfile.read())
            url = self.url(routes.profile, pname=self.name)
            self._http.put_binary(url, data.getvalue(), headers)

    def delete(self):
        return self.route_request(routes.profile_delete, pname=self.name)

    def new_from_livecd(self, isoname, additional_kargs=""):
        """Creates a profile from a livecd
        """
        self.logger.debug("Creating profile from ISO: %s" % isoname)
        self.logger.debug("  Additional kargs: %s" % additional_kargs)
        check_isfile(isoname)

        subprocess.check_call(["sudo", "livecd-iso-to-pxeboot", isoname])

        # Build kargs
        with open("tftpboot/pxelinux.cfg/default") as cfg:
            kargs = []
            for line in cfg:
                if "APPEND" in line:
                    kargs = re.split("\s+", line.strip())[1:]
        kargs = [karg for karg in kargs
                 if re.match("(root|ro|live|check|rhgb|quiet|rd)", karg)]
        kargs.append(additional_kargs.strip())
        kargs = " ".join(kargs)

        self.new("tftpboot/vmlinuz0", "tftpboot/initrd0.img", kargs)

        if os.path.isdir("tftpboot"):
            subprocess.check_call(["sudo", "rm", "-rvf", "tftpboot"])


class TestplanAPI(IgordAPI):
    """An interface to the testplan related REST-API
    """
    def __init__(self, host, port, name):
        super(TestplanAPI, self).__init__(host, port)
        self.name = name

    def start(self, substitutions={}):
        url = self.url(routes.testplan_start, query=substitutions,
                       name=self.name)
        return self.request(url)

    def abort(self):
        return self.route_request(routes.testplan_abort, name=self.name)

    def status(self):
        return self.route_request(routes.testplan_status, name=self.name)

    def report(self):
        return self.route_request(routes.testplan_report, name=self.name)

    def report_junit(self):
        return self.route_request(routes.testplan_report_junit, name=self.name)
