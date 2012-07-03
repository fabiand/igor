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
import utils

logger = logging.getLogger(__name__)


class ProfileOrigin(testing.Origin):
    """This is the source where igor retrieves cobbler profiles
    """
    cobbler = None

    def __init__(self, server_url, user, pw, ssh_uri):
        self.cobbler = Cobbler(server_url, (user, pw), ssh_uri)

    def name(self):
        return "CobblerProfilesOrigin(%s)" % self.cobbler.server_url

    def items(self):
        items = {}
        with self.cobbler as remote:
            for c_pname in remote.profiles():
                i_profile = Profile(remote, c_pname)
                i_profile.origin = self
                items[c_pname] = i_profile
        return items

    def create_item(self, pname, kernel_file, initrd_file, kargs_file):
        profile = Profile(self.cobbler, pname)
        profile.populate_with(kernel_file, initrd_file, kargs_file)


class HostsOrigin(testing.Origin):
    """This is the source where igor retrieves cobbler systems as hosts
    """
    cobbler = None
    expression = None

    def __init__(self, server_url, user, pw, ssh_uri, expression="igor-"):
        self.cobbler = Cobbler(server_url, (user, pw), ssh_uri)
        self.expression = expression

    def name(self):
        return "CobblerHostsOrigin(%s)" % self.cobbler.server_url

    def items(self):
        items = {}
        with self.cobbler as remote:
            for sysname in remote.systems():
                if self.expression in sysname:
                    continue
                host = Host()
                host.remote = remote
                host.name = sysname
                host.origin = self
                host.mac = None
                items[sysname] = host
        logger.debug("Number of cobbler hosts: %s" % len(items))
#        logger.debug("Hosts: %s" % items)
        return items


class Host(hosts.RealHost):
    """Implemets the methods required by testing.Host
    """
    remote = None

    def start(self):
        logger.debug("Powering on %s" % self.get_name())
        with self.remote as s:
            s.power_system(self.get_name(), "off")
            time.sleep(60)
            s.power_system(self.get_name(), "on")

    def purge(self):
        logger.debug("Powering off %s" % self.get_name())
        with self.remote as s:
            s.power_system(self.get_name(), "off")


class Profile(testing.Profile):
    remote = None
    name = None
    additional_args = None

    system_existed = False
    previous_profile = None

    remote_path = None
    identification_tag = "managed-by-igor"

    def __init__(self, remote, profile_name):
        self.remote = remote
        self.name = profile_name

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

    def delete(self):
        self.remote_path = "/tmp/igor-cobbler-%s" % self.get_name()
        self.__ssh_remove_remote_distro_profile_and_files(self.remote_path)

    def populate_with(self, vmlinuz, initrd, kargs):
        self.remote_path = "/tmp/igor-cobbler-%s" % self.get_name()
        self.__scp_files_to_remote(self.remote_path, vmlinuz, initrd, kargs)
        self.__ssh_create_remote_distro_and_profile(self.remote_path, \
                                                    vmlinuz, initrd, kargs)

    def __scp_files_to_remote(self, remote_path, vmlinuz, initrd, kargs):
        cmd = """
            ssh {url} "mkdir -p '{remote_path}'"
            scp "{vmlinuz}" "{initrd}" "{kargs}" "{url}:/{remote_path}/"
        """.format(
                url=self.remote.ssh_uri,
                remote_path=remote_path,
                profilename=self.get_name(),
                vmlinuz=vmlinuz,
                initrd=initrd,
                kargs=kargs
                )
        utils.run(cmd)

    def __ssh_create_remote_distro_and_profile(self, remote_path, vmlinuz, \
                                               initrd, kargs):
        cmd = """
            ssh {remote_url} '
                cobbler distro add \\
                    --name=\"{profilename}-distro\" \\
                    --kernel=\"{vmlinuz}\" \\
                    --initrd=\"{initrd}\" \\
                    --kopts=\"$(cat {kargs})\" \\
                    --arch=\"{arch}\" \\
                    --breed=\"other\" \\
                    --os-version=\"\"

                cobbler profile add \\
                    --name=\"{profilename}\" \\
                    --distro=\"{profilename}-distro\" \\
                    --kickstart=\"\" \\
                    --repos=\"\" \\
                    --comment=\"{identification_tag}\"
                '
        """.format(
            remote_url=self.remote.ssh_uri,
            profilename=self.get_name(),
            vmlinuz=os.path.join(remote_path, os.path.basename(vmlinuz)),
            initrd=os.path.join(remote_path, os.path.basename(initrd)),
            kargs=os.path.join(remote_path, os.path.basename(kargs)),
#            kargs=open(kargs).read().strip(),
            arch="x86_64",
            identification_tag=self.identification_tag
            )
        utils.run(cmd)

    def __ssh_remove_remote_distro_profile_and_files(self, remote_path):
        profile_comment = self.remote.profile(self.get_name())["comment"]
        if self.identification_tag not in profile_comment:
            raise Exception("Profile '%s' is not managed y igor" % \
                            self.get_name())
        cmd = """
            ssh {remote_url} "
                cobbler distro remove --name=\"{profilename}-distro\"
                cobbler profile remove --name=\"{profilename}\"
                rm -v \"{remote_path}\"/*
                rmdir -v \"{remote_path}\"
                "
        """.format(
            remote_url=self.remote.ssh_uri,
            remote_path=remote_path,
            profilename=self.get_name()
            )
        utils.run(cmd)

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
    ssh_uri = None
    token = None

#        "http://cobbler-server.example.org/cobbler_api"
    def __init__(self, server_url, c, ssh_uri):
        self.credentials = c
        self.server_url = server_url
        self.server = xmlrpclib.Server(server_url)
        self.ssh_uri= ssh_uri

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

    def profile(self, name):
        return self.server.get_blended_data(name, "")

    def systems(self):
        return [e["name"] for e in self.server.get_systems(self.token, \
                                                    1, 1000)]

    def system(self, name):
        return self.server.get_blended_data("", name)

    def power_system(self, name, power):
        assert power in ["on", "off"]
        return self.server.background_power_system(power, self.token)


def example():
    c = Cobbler("http://127.0.0.1/cobbler_api")
    c.login()
    print (s.systems())
    print (s.profiles())

    p = c.new_profile("abc")
