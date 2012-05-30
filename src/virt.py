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
        cmd = "nice time qemu-img convert -c -O %s '%s' '%s'" % (dst_fmt, self.filename, dst_filename)
        run(cmd)
        cmd = "mv '%s' '%s'" % (dst_filename, self.filename)
        run(cmd)
        self.format = dst_fmt


class VMHost(Host):
    '''A host which is actually a virtual guest.

    VMHosts are not much different from other hosts, besides that we can configure them.
    '''
    name = None
    session = None
    image_specs = None

    poolname = "default"
    network_configuration = "network=default"

    vm_prefix = "igor-vm-"
    vm_defaults = None

    connection_uri = "qemu:///system"
    libvirt_vm_definition = None

    def __init__(self, *args, **kwargs):
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
                image_spec.create(self.session.dirname)

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
            "os-type": "'linux'",
            "boot": "network",
            "network": self.network_configuration,
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
            cmd += " --disk vol=%s,device=disk,bus=virtio,format=raw" % poolvol

        self.libvirt_vm_definition = run(cmd)

#        logger.debug(self.libvirt_vm_definition)

        self.define()

    def _virsh(self, cmd):
        run("virsh --connect='%s' %s" % (self.connection_uri, cmd))

    def _upload_image(self, image_spec):
        image_spec.compress()
        disk = image_spec.filename
        volname = os.path.basename(disk)
        poolvol = "%s/%s" % (self.poolname, volname)
        logger.debug("Uploading disk image '%s' to '%s'" % (disk, poolvol))
        self._virsh("vol-create-as --name '%s' --capacity '%s' --format %s --pool '%s'" % (volname, image_spec.size, image_spec.format, self.poolname))
        self._virsh("vol-upload --vol '%s' --file '%s' --pool '%s'" % (volname, disk, self.poolname))
        return poolvol

    def get_name(self):
        return self._vm_name

    def get_mac_address(self):
        dom = etree.XML(self.libvirt_vm_definition)
        mac = dom.xpath("/domain/devices/interface[1]/mac")[0]
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
                volname = os.path.basename(image_spec.filename)
                self._virsh("vol-delete --vol '%s' --pool '%s'" % (volname, self.poolname))

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

    def define(self):
        tmpfile = run("mktemp --tmpdir")
        with open(tmpfile, "w") as f:
            logger.debug(tmpfile)
            f.write(self.libvirt_vm_definition)
            f.flush()
            self._virsh("define %s" % tmpfile)

    def undefine(self):
        self._virsh("undefine %s" % self._vm_name)


class VMHostFactory:
    @staticmethod
    def create_default_host(connection_uri="qemu:///system", \
                            storage_pool="default", \
                            network_configuration="network=default"):
        host = VMHost(name="8g-gpt-1g", image_specs=[ \
                 VMImage("2G", [ \
                   Partition("pri", "1M", "1G") \
                 ]) \
               ])
        host.connection_uri = connection_uri
        host.storage_pool = storage_pool
        host.network_configuration = network_configuration
        return host
