# -*- coding: utf-8 -*-
#
# Copyright (C) 2012  Red Hat, Inc.
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

import logging
import xmlrpclib
import time
import os

import testing
import hosts

logger = logging.getLogger(__name__)


class CobblerProfileOrigin(testing.Origin):
    cobbler = None
    kargs = None
    kargs_post = None

    def __init__(self, server_url, user, pw, kargs, kargs_post):
        self.cobbler = Cobbler(server_url, (user, pw))
        self.kargs = kargs
        self.kargs_post = kargs_post

    def name(self):
        return "CobblerProfilesOrigin(%s)" % self.cobbler.server_url

    def items(self):
        items = {}
        with self.cobbler.new_session() as cblr_sess:
            for cpname in cblr_sess.profiles():
                iprofile = self._igor_profile_from_cobbler_profile(cpname)
                iprofile.origin = self
                items[cpname] = iprofile
        logger.debug("Number of profiles: %s" % len(items))
#        logger.debug("Profiles: %s" % items)
        return items

    def _igor_profile_from_cobbler_profile(self, cprofile):
        return self.cobbler.new_profile(cprofile, {
            "kernel_options": " ".join([self.kargs, self.kargs_post]),
            "kernel_options_post": self.kargs,
        })

    # def lookup could be done w/ cobbler native functions

    def create_item(self, pname, kernel_file, initrd_file, kargs_file, \
                        kargs_post_file):
        profile = self.cobbler.new_profile(pname)
        profile.populate_with(kernel_file, initrd_file, kargs_file, \
                              kargs_post_file)


#pydoc cobbler.remote
class Cobbler(object):
    """A simple wrapper around Cobbler's XMLRPC API.

    Cobbler also provides it's own python bindings but those are just
    distributed with all the other stuff. This small wrapper can be used
    as long as the bindigs are not split from the rest.
    """
    server_url = None
    server = None
    credentials = None

    def __init__(self, server_url, c=("cobbler", "cobbler")):
#        "http://cobbler-server.example.org/cobbler_api"
        self.credentials = c
        self.server_url = server_url
        self.server = xmlrpclib.Server(server_url)

    def new_session(self):
        return Cobbler.Session(self.server, self.credentials)

    def new_profile(self, profile_name, additional_args=None):
        return Cobbler.Profile(self.new_session, profile_name, \
                               additional_args)

    class Profile(testing.Profile):
        cobbler_session_cb = None
        name = None
        additional_args = None

        system_existed = False
        previous_profile = None

        def __init__(self, cobbler_session_cb, profile_name, additional_args):
            self.cobbler_session_cb = cobbler_session_cb
            self.name = profile_name
            self.additional_args = additional_args

        def get_name(self):
            return self.name

        def assign_to(self, host):
            with self.cobbler_session_cb() as session:
                if self.name not in session.profiles():
                    logger.info("Available profiles: %s" % session.profiles())
                    raise Exception("Unknown profile '%s'" % (self.name))

                additional_args = {}
                for k, v in self.additional_args.items():
                    additional_args[k] = v.format(
                            igor_cookie=host.session.cookie
                        )

                system_handle = self.__get_or_create_system(session, \
                                                            host.get_name())

                session.assign_defaults(system_handle, \
                                        name=host.get_name(), \
                                        mac=host.get_mac_address(), \
                                        profile=self.name, \
                                        additional_args=additional_args)

                session.set_netboot_enable(host.get_name(), True)

        def __get_or_create_system(self, session, name):
            system_handle = None
            if name in session.systems():
                logger.info("Reusing existing system %s" % name)
                system_handle = session.get_system(name)
                self.previous_profile = session.get_system(name)["profile"]
            else:
                system_handle = session.new_system()
            return system_handle

        def enable_pxe(self, host, enable):
            with self.cobbler_session_cb() as session:
                session.set_netboot_enable(host.get_name(), enable)

        def set_kargs(self, host, kargs):
            raise Exception("Not yet implemented")
            #with self.cobbler_session_cb() as session:
                #session.modify_system(system_id,"kernel_options", v,
                #                      self.token)

        def revoke_from(self, host):
            name = host.get_name()
            logger.debug("Revoking host '%s' from cobbler " % name)
            with self.cobbler_session_cb() as session:
                if name in session.systems():
                    if self.system_existed:
                        logger.info(("Not removing system %s because it " + \
                                     "existed before") % name)
                        system_handle = session.get_system_handle(name)
                        session.modify_system(system_handle, {
                            "profile": self.previous_profile
                        })
                    else:
                        session.remove_system(name)
                else:
                    # Can happen if corresponding distro or profile was deleted
                    logger.info(("Unknown '%s' host when trying to revoke " + \
                                 "igor profile.") % name)

        def populate_with(self, vmlinuz, initrd, kargs):
            remote_path = "/tmp/"
            self.__scp_files_to_remote(remote_path, vmlinuz, initrd, kargs)
            self.__ssh_create_remote_distro_and_profile(remote_path, vmlinuz, initrd, kargs)

        def __scp_files_to_remote(self, remote_path, vmlinuz, initrd, kargs):
            cmd = """
                scp {vmlinuz} {initrd} {kargs} {remote_url}/tmp/igor-{profilename}
            """.format(
                    profilename=self.get_name(),
                    vmlinuz=vmlinuz,
                    initrd=initrd,
                    kargs=kargs,
                    remote_url="FIXME"
                    )

        def __ssh_create_remote_distro_and_profile(self, remote_path, vmlinuz, initrd, kargs):
            cmd = """
                cobbler distro add \
                    --name="{profilename}-distro" \
                    --kernel="{vmlinuz}" \
                    --initrd="{initrd}" \
                    --kopts="{kargs}" \
                    --arch="{arch}" \
                    --breed="other" \
                    --os-version=""

                cobbler profile add \
                    --name="{profilename}" \
                    --distro="{profilename}-distro" \
                    --kickstart="" \
                    --repos=""
            """.format(
                profilename=self.get_name(),
                vmlinuz=os.path.join(remote_path, vmlinuz),
                initrd=os.path.join(remote_path, initrd),
                kargs=os.path.join(remote_path, kargs),
                arch="x86_64"
                )
            logger.debug("On remote: %s" % cmd)

    class Session:
        """Helper to login and sync
        """
        server = None
        credentials = None
        token = None

        def __init__(self, server, credentials):
            self.server = server
            self.credentials = credentials
            self.login()

        def __enter__(self):
            self.login()
            return self

        def __exit__(self, type, value, traceback):
            pass

        def login(self):
            self.token = self.server.login(*(self.credentials))

        def sync(self):
            logger.debug("Syncing")
            self.server.sync(self.token)

        def assign_defaults(self, system_handle, name, mac, profile, \
                            additional_args):
            args = {
                "name": name,
                "mac": mac,
                "profile": profile,
                "status": "testing",
                "kernel_options": "",
                "kernel_options_post": "",
                "modify_interface": {
                    "macaddress-eth0": mac
                }
            }

            if additional_args is not None:
                logger.debug("Adding additional args: %s" % additional_args)
                args.update(additional_args)

            self.modify_system(system_handle, args)

        def new_system(self):
            """Add a new system.
            """
            logger.debug("Adding a new system")
            return self.server.new_system(self.token)

        def get_system_handle(self, name):
            return self.server.get_system_handle(name, self.token)

        def modify_system(self, system_handle, args):
            for k, v in args.items():
                logger.debug("Modifying system: %s=%s" % (k, v))
                self.server.modify_system(system_handle, k, v, self.token)

            self.server.save_system(system_handle, self.token)

        def set_netboot_enable(self, name, pxe):
            """(Un-)Set netboot.
            """
            args = {
                "netboot-enabled": 1 if pxe else 0
            }

            system_handle = self.get_system_handle(name)
            self.modify_system(system_handle, args)

        def remove_system(self, name):
            self.server.remove_system(name, self.token)

        def profiles(self):
            return [e["name"] for e in self.server.get_profiles(self.token, \
                                                        1, 1000)]

        def systems(self):
            return [e["name"] for e in self.server.get_systems(self.token, \
                                                        1, 1000)]

        def system(self, name):
            return self.server.get_system(self.token, name)

        def power_system(self, name, power):
            assert power in ["on", "off"]
            return self.server.background_power_system(power, self.token)


class CobblerHost(hosts.RealHost):
    remote = None

    def start(self):
        logger.debug("Powering on %s" % self.get_name())
        with self.remote.new_session() as s:
            s.power_system(self.get_name(), "off")
            time.sleep(60)
            s.power_system(self.get_name(), "on")

    def purge(self):
        logger.debug("Powering off %s" % self.get_name())
        with self.remote.new_session() as s:
            s.power_system(self.get_name(), "off")


class CobblerHostsOrigin(testing.Origin):
    cobbler = None
    kargs = None
    kargs_post = None
    expression = None

    def __init__(self, server_url, user, pw, kargs, kargs_post, expression="igor-"):
        self.cobbler = Cobbler(server_url, (user, pw))
        self.kargs = kargs
        self.kargs_post = kargs_post
        self.expression = expression

    def name(self):
        return "CobblerHostsOrigin(%s)" % self.cobbler.server_url

    def items(self):
        items = {}
        with self.cobbler.new_session() as cblr_sess:
            for sysname in cblr_sess.systems():
                if self.expression in sysname:
                    continue
                host = CobblerHost()
                host.remote = self.cobbler
                host.name = sysname
                host.origin = self
                host.mac = None
                items[sysname] = host
        logger.debug("Number of cobbler hosts: %s" % len(items))
#        logger.debug("Hosts: %s" % items)
        return items


def example():
    c = Cobbler("http://127.0.0.1/cobbler_api")
    s = c.new_session()
    print (s.systems())
    print (s.profiles())

    p = c.new_profile("abc")
