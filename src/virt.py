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


def virsh(cmd):
    run("virsh --connect='qemu:///system' %s" % cmd)

class VMImage(Layout):
    pass

class VMHost(Host):
    '''A host which is actually a virtual guest.

    VMHosts are not much different from other hosts, besides that we can configure them.
    '''
    name = None
    session = None
    image_specs = None

    disk_images = None

    vm_prefix = "igor-vm-"
    vm_defaults = None

    connection_uri = "qemu:///system"
    libvirt_vm_definition = None

    def __init__(self, *args, **kwargs):
        self.disk_images = []
        self.vm_defaults = {}
        Host.__init__(self, *args, **kwargs)

    def prepare(self, session):
        logger.debug("Preparing VMHost")
        self.session = session
        self._vm_name = "%s%s-%s" % (self.vm_prefix, self.name, self.session.cookie)
        self.prepare_images()
        self.prepare_vm()

    def prepare_images(self):
        logger.debug("Preparing images")
        if self.image_specs is None or len(self.image_specs) is 0:
            logger.info("No image spec given.")
        else:
            for image_spec in self.image_specs:
                self.disk_images.append(image_spec.create(self.session.dirname))

    def prepare_vm(self):
        """Define the VM within libvirt
        """
        logger.debug("Preparing vm")

        # Sane defaults
        virtinstall_args = {
            "connect": "'%s'" % self.connection_uri,
            "name": "'%s'" % self._vm_name,
            "vcpus": "2",
            "cpu": "host",
            "ram": "768",
            "boot": "network",
            "os-type": "'linux'",
            "noautoconsole": None,      # Prevents opening a window
            "import": None,
            "dry-run": None,
            "print-xml": None
        }

        virtinstall_args.update(self.vm_defaults)

        cmd = "virt-install "
        cmd += dict_to_args(virtinstall_args)

        for disk in self.disk_images:
            cmd += " --disk path='%s',device=disk,bus=virtio,format=raw" % disk

        self.libvirt_vm_definition = run(cmd)

#        logger.debug(self.libvirt_vm_definition)

        self.define()

    def get_name(self):
        return self._vm_name

    def get_mac_address(self):
        dom = etree.XML(self.libvirt_vm_definition)
        mac = dom.xpath("/domain/devices/interface[@type='network'][1]/mac")[0]
        return mac.attrib["address"]

    def start(self):
        self.boot()

    def purge(self):
        self.remove()

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
        virsh("start %s" % self._vm_name)

    def reboot(self):
        virsh("reboot %s" % self._vm_name)

    def shutdown(self):
        virsh("shutdown %s" % self._vm_name)

    def destroy(self):
        virsh("destroy %s" % self._vm_name)

    def define(self):
        tmpfile = run("mktemp --tmpdir")
        with open(tmpfile, "w") as f:
            logger.debug(tmpfile)
            f.write(self.libvirt_vm_definition)
            f.flush()
            virsh("define %s" % tmpfile)

    def undefine(self):
        virsh("undefine %s" % self._vm_name)


class VMHostFactory:
    @staticmethod
    def create_default_host(connection_uri=None):
        host = VMHost(name="8g-gpt-1g", image_specs=[ \
                 VMImage("8G", [ \
                   Partition("pri", "1M", "1G") \
                 ]) \
               ])
        if connection_uri:
            host.connection_uri = connection_uri
        return host
