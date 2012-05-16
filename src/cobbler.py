# -*- coding: utf-8 -*-

import logging
import xmlrpclib

import testing

logger = logging.getLogger(__name__)


#pydoc cobbler.remote
class Cobbler(object):
    """A simple wrapper around Cobbler's XMLRPC API.

    Cobbler also provides it's own python bindings but those are just
    distributed with all the other stuff. This small wrapper can be used
    as long as the bindigs are not split from the rest.
    """
    server = None
    credentials = None

    def __init__(self, server_url, c=("cobbler", "cobbler")):
#        "http://cobbler-server.example.org/cobbler_api"
        self.credentials = c
        self.server = xmlrpclib.Server(server_url)

    def new_session(self):
        return Cobbler.Session(self.server, self.credentials)

    def new_profile(self, profile_name):
        return Cobbler.Profile(self.new_session(), profile_name)

    class Session:
        """Helper to login and sync
        """
        server = None
        credentials = None
        token = None

        def __init__(self, server, credentials):
            self.server = server
            self.credentials = credentials
            self.token = server.login(*(credentials))

        def __enter__(self):
            return self

        def __exit__(self, type, value, traceback):
            self.server.sync(self.token)

        def add_system(self, name, mac, profile):
            """Add a new system.
            """
            args = {
                "name": name,
                "mac": mac,
                "profile": profile,
                "status": "testing",
                "kernel_options": "BOOTIF=eth0 storage_init firstboot",
                "modify_interface": {
                    "macaddress-eth0": mac
                }
            }

            system_id = self.server.new_system(self.token)

            for k, v in args.items():
                logger.debug("Modifying system: %s %s" % (k, v))
                self.server.modify_system(system_id, k, v, self.token)

            self.server.save_system(system_id, self.token)

        def set_netboot_enable(self, name, pxe):
            """(Un-)Set netboot.
            """
            args = {
                "netboot-enabled": 1 if pxe else 0
            }

            system_handle = self.server.get_system_handle(name, self.token)

            for k, v in args.items():
                logger.debug("Modifying system: %s %s" % (k, v))
                self.server.modify_system(system_handle, k, v, self.token)

            self.server.save_system(system_handle, self.token)

        def remove_system(self, name):
            self.server.remove_system(name, self.token)

        def get_profiles(self):
            return [e["name"] for e in self.server.get_systems(s.token)]

        def get_systems(self):
            return [e["name"] for e in self.server.get_profiles(s.token)]

    class Profile(testing.Profile):
        session = None
        name = None

        def __init__(self, cobbler_session, profile_name):
            self.session = cobbler_session
            self.name = profile_name

        def assign_to(self, host):
            with self.session as session:
                if self.name not in session.get_profiles():
                    raise Exception("Profile '%s' unknown to server." % self.name)
                session.add_system(host.get_name(), host.get_mac_address(), \
                                   self.name)
                session.set_netboot_enable(host.get_name(), True)

        def revoke_from(self, host):
            with self.session as session:
                if host.get_name() not in session.get_systems():
                    raise Exception("Host '%s' unknown to server." % self.name)
                session.remove_system(host.get_name())

if __name__ == '__main__':
    c = Cobbler("http://127.0.0.1:25151/")
    s = c.new_session()
    print (s.get_systems())
    print (s.get_profiles())

    p = c.new_profile("abc")
