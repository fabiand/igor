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

import os
import re
import logging
from lxml import etree
import tempfile

import igor.main
from igor.utils import run, dict_to_args
import igor.partition


logger = logging.getLogger(__name__)


class VMImage(igor.partition.Layout):
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


class LibvirtConnection(object):
    connection_uri = None

    def virsh(self, cmd):
        return LibvirtConnection._virsh(cmd, self.connection_uri)

    @staticmethod
    def _virsh(cmd, connection_uri):
        return run("virsh --connect='%s' %s" % (connection_uri, cmd))


class VMHost(igor.main.Host):
    """Corresponds to a libvirt domain.
    This class can be used to control the domain and wrap it to provide
    the igor Host API.
    """

    _vm_name = None
    connection_uri = "qemu:///system"
    poolname = "default"

    def __init__(self, name, remove=True, *args, **kwargs):
        self._vm_name = name
        self.remove_afterwards = remove
        super(VMHost, self).__init__(*args, **kwargs)

    def _virsh(self, cmd):
        return LibvirtConnection._virsh(cmd, self.connection_uri)

    def start(self):
        self.boot()

    def get_name(self):
        return self._vm_name

    def get_mac_address(self):
        dom = etree.XML(self.dumpxml())
        mac = dom.xpath("/domain/devices/interface[1]/mac")[0]
        return mac.attrib["address"]

    def get_disk_images(self):
        path = ("/domain/devices/disk[@type='file' and @device='disk']" +
                "/source/@file")
        dom = etree.XML(self.dumpxml())
        files = dom.xpath(path)
        return files

    def prepare(self):
        """No need to prepare, host is assumed to exist
        """
        pass

    def purge(self):
        if self.remove_afterwards:
            self.remove()
        else:
            logger.debug("VMHost shall not be removed at the end.")

    def remove_images(self):
        for image in self.get_disk_images():
            volname = os.path.basename(image)
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


class NewVMHost(VMHost):
    '''A host which is actually a virtual guest.
    VMHosts are not much different from other hosts, besides that we can
    configure them.
    '''
    name = None

    image_specs = None

    network_configuration = "network=default"
    disk_bus_type = "virtio"

    vm_prefix = "i-"
    description = "managed-by-igor"
    vm_defaults = None

    def __init__(self, force_name=None, *args, **kwargs):
        self.vm_defaults = {}
        self._vm_name = "VMHost (Created on demand)"
        self.force_name = force_name
        super(NewVMHost, self).__init__(*args, **kwargs)

    def prepare(self):
        logger.debug("Preparing a new VMHost")
        self._vm_name = "%s%s-%s" % (self.vm_prefix, self.name, \
                                     self.session.cookie)
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
        name = self.force_name or self._vm_name
        logger.debug("Preparing vm: %s" % name)

        # Sane defaults
        virtinstall_args = {
            "connect": "'%s'" % self.connection_uri,
            "name": "'%s'" % name,
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

    def remove_images(self):
        # Remove or local images (created initially)
        if self.image_specs is None or len(self.image_specs) is 0:
            logger.info("No image spec given.")
        else:
            for image_spec in self.image_specs:
                image_spec.remove()
        # Now also remove the remote volumes
        super(NewVMHost, self).remove_images()


class VMHostFactory:
    @staticmethod
    def create_default_host(connection_uri="qemu:///system", \
                            storage_pool="default", \
                            network_configuration="network=default"):
        host = NewVMHost(name="default", image_specs=[ \
                 VMImage("8G", [ \
                   igor.partition.Partition("pri", "1M", "1G") \
                 ]) \
               ])
        host.connection_uri = connection_uri
        host.storage_pool = storage_pool
        host.network_configuration = network_configuration
        return host

    @staticmethod
    def create_or_reuse_host(name, remove=False):
        """Creates or reuses a virtual guest and cond. removes it at the end

        Args:
            name: Name to be used
            remove: If the guest shall be removed at the end
        """


class CommonLibvirtHostOrigin(igor.main.Origin):
    connection_uri = None
    storage_pool = None
    network_configuration = None

    def __init__(self, connection_uri, storage_pool, network_configuration):
        self.connection_uri = connection_uri
        self.storage_pool = storage_pool
        self.network_configuration = network_configuration

    def items(self):
        return NotImplementedError


class VMAlwaysCreateHostOrigin(CommonLibvirtHostOrigin):
    def name(self):
        return "VMAlwaysCreateHostOrigin(%s)" % str(self.__dict__)

    def _build_host(self):
        return VMHostFactory.create_default_host( \
                   connection_uri=self.connection_uri, \
                   storage_pool=self.storage_pool, \
                   network_configuration=self.network_configuration)

    def items(self):
        hosts = {"default-libvirt": self._build_host()}
        for key in hosts:
            hosts[key].origin = self
        return hosts


class VMUseExistingHostOrigin(CommonLibvirtHostOrigin):
    """Provides access to all existing guests
    """

    def name(self):
        return "VMCreateOrReuseHostOrigin(%s)" % str(self.__dict__)

    def _list_domains(self):
        domains = []
        cmd = "list --all"
        domain_pattern = re.compile("\s+(\d+)\s+([\w-]+)\s+(\w+.*$)")
        txt = LibvirtConnection._virsh(cmd, self.connection_uri)
        for line in txt:
            groups = domain_pattern.search(line)
            if groups:
                domid, domname, state = groups
                if state in ["running", "shut off"]:
                    domains.append(domname)
        return domains

    def items(self):
        domains = self._list_domains()
        logger.debug("Found the following existing domains: %s" % domains)
        hosts = {n: VMHost(n) for n in domains}
        for key in hosts:
            hosts[key].origin = self
        return hosts
