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
# -*- coding: utf-8 -*-

import logging
import os
from string import Template
from lxml import etree
import tempfile

import libvirt

from testing import *
from utils import run, dict_to_args
from partition import *


logger = logging.getLogger(__name__)


class VMImage(Layout):
    def compress(self, dst_fmt="qcow2"):
        '''Convert the raw image into a qemu image.
        '''
        assert dst_fmt in ["raw", "qcow2"], "Only qcow2 and raw allowed"

        dst_filename = "%s.%s" % (self.filename, dst_fmt)
        cmd = "nice time qemu-img convert -c -O %s '%s' '%s'" % (dst_fmt, \
                                                   self.filename, dst_filename)
        run(cmd)
        cmd = "mv '%s' '%s'" % (dst_filename, self.filename)
        run(cmd)
        self.format = dst_fmt


class VMHost(Host):
    '''A host which is actually a virtual guest.
    VMHosts are not much different from other hosts, besides that we can
    configure them.
    '''
    name = None
    image_specs = None

    poolname = "default"
    network_configuration = "network=default"
    disk_bus_type = "virtio"

    vm_prefix = "i-"
    description = "managed-by-igor"
    vm_defaults = None
    _vm_name = None

    connection_uri = "qemu:///system"

    def __init__(self, *args, **kwargs):
        self.vm_defaults = {}
        self._vm_name = "VMHost (Created on demand)"
        Host.__init__(self, *args, **kwargs)

    def prepare(self):
        logger.debug("Preparing VMHost")
        self._vm_name = "%s%s-%s" % (self.vm_prefix, self.name, \
                                     self.session.cookie)
        self.prepare_images()
        self.prepare_vm()

    def start(self):
        self.boot()

    def get_name(self):
        return self._vm_name

    def get_mac_address(self):
        dom = etree.XML(self.dumpxml())
        mac = dom.xpath("/domain/devices/interface[1]/mac")[0]
        return mac.attrib["address"]

    def purge(self):
        self.remove()

    def prepare_images(self):
        logger.debug("Preparing images")
        if self.image_specs is None or len(self.image_specs) is 0:
            logger.info("No image spec given.")
        else:
            for image_spec in self.image_specs:
                image_spec.create(self.session.dirname)

    def prepare_vm(self):
        """Define the VM within libvirt
        """
        logger.debug("Preparing vm")

        # Sane defaults
        virtinstall_args = {
            "connect": "'%s'" % self.connection_uri,
            "name": "'%s'" % self._vm_name,
            "description": "'%s'" % self.description,
            "vcpus": "2",
            "cpu": "host",
            "ram": "1024",
            "os-type": "linux",
            "boot": "network",
            "network": self.network_configuration,
            "graphics": "spice",
            "video": "vga",
            "channel": "spicevmc",
            "noautoconsole": None,      # Prevents opening a window
            "import": None,
            "dry-run": None,
            "print-xml": None
        }

        virtinstall_args.update(self.vm_defaults)

        cmd = "virt-install "
        cmd += dict_to_args(virtinstall_args)

        for image_spec in self.image_specs:
            poolvol = self._upload_image(image_spec)
            cmd += " --disk vol=%s,device=disk,bus=%s,format=%s" % (poolvol, \
                                         self.disk_bus_type, image_spec.format)

        definition = run(cmd)

        self.define(definition)

    def _virsh(self, cmd):
        return run("virsh --connect='%s' %s" % (self.connection_uri, cmd))

    def _upload_image(self, image_spec):
        image_spec.compress()
        disk = image_spec.filename
        volname = os.path.basename(disk)
        poolvol = "%s/%s" % (self.poolname, volname)
        logger.debug("Uploading disk image '%s' to new volume '%s'" % (disk, \
                                                                      poolvol))
        self._virsh(("vol-create-as --name '%s' --capacity '%s' " + \
                     "--format %s --pool '%s'") % (volname, image_spec.size, \
                                                 image_spec.format, \
                                                 self.poolname))
        self._virsh("vol-upload --vol '%s' --file '%s' --pool '%s'" % ( \
                                                 volname, disk, self.poolname))
        return poolvol

    def start_vm_and_install_os(self):
        # Never reboot, even if requested by guest
        self.set_reboot_is_poweroff(True)

        self.boot()

    def remove_images(self):
        if self.image_specs is None or len(self.image_specs) is 0:
            logger.info("No image spec given.")
        else:
            for image_spec in self.image_specs:
                image_spec.remove()
                volname = os.path.basename(image_spec.filename)
                self._virsh("vol-delete --vol '%s' --pool '%s'" % (volname, \
                                                                self.poolname))

    def remove_vm(self):
        self.destroy()
        self.undefine()

    def remove(self):
        '''
        Remove all files which were created during the VM creation.
        '''
        logger.debug("Removing host %s" % self._vm_name)
        self.remove_vm()
        self.remove_images()

    def boot(self):
        self._virsh("start %s" % self._vm_name)

    def reboot(self):
        self._virsh("reboot %s" % self._vm_name)

    def shutdown(self):
        self._virsh("shutdown %s" % self._vm_name)

    def destroy(self):
        self._virsh("destroy %s" % self._vm_name)

    def define(self, definition):
        with tempfile.NamedTemporaryFile() as f:
            logger.debug(f.name)
            f.write(definition)
            f.flush()
            self._virsh("define '%s'" % f.name)

    def undefine(self):
        self._virsh("undefine %s" % self._vm_name)

    def dumpxml(self):
        return self._virsh("dumpxml '%s'" % self._vm_name)


class VMHostFactory:
    @staticmethod
    def create_default_host(connection_uri="qemu:///system", \
                            storage_pool="default", \
                            network_configuration="network=default"):
        host = VMHost(name="8g-gpt-1g", image_specs=[ \
                 VMImage("8G", [ \
                   Partition("pri", "1M", "1G") \
                 ]) \
               ])
        host.connection_uri = connection_uri
        host.storage_pool = storage_pool
        host.network_configuration = network_configuration
        return host

    @staticmethod
    def hosts_from_configfile():
        pass


class VMAlwaysCreateHostOrigin(Origin):
    connection_uri = None
    storage_pool = None
    network_configuration = None

    def __init__(self, connection_uri, storage_pool, network_configuration):
        self.connection_uri = connection_uri
        self.storage_pool = storage_pool
        self.network_configuration = network_configuration

    def name(self):
        return "VMAlwaysCreateHostOrigin(%s)" % str(self.__dict__)

    def items(self):
        hosts = {"default-libvirt": \
                            VMHostFactory.create_default_host( \
                            connection_uri=self.connection_uri, \
                            storage_pool=self.storage_pool, \
                            network_configuration=self.network_configuration)
               }
        for key in hosts:
            hosts[key].origin = self
        return hosts
