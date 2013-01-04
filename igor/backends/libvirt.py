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

from igor.utils import run, dict_to_args
from lxml import etree
import igor.main
import igor.partition
import logging
import os
import re
import tempfile
import time



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
        return run("LC_ALL=C virsh --connect='%s' %s" % (connection_uri, cmd))


class VMHost(igor.main.Host):
    """Corresponds to a libvirt domain.
    This class can be used to control the domain and wrap it to provide
    the igor Host API.
    """

    vm_name = None
    connection_uri = "qemu:///system"
    poolname = "default"

    remove_afterwards = True

    def __init__(self, name, remove=True):
        super(VMHost, self).__init__()
        self.vm_name = name
        self.remove_afterwards = remove

    def _virsh(self, cmd):
        return LibvirtConnection._virsh(cmd, self.connection_uri)

    def start(self):
        self.boot()

    def get_name(self):
        return self.vm_name

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
        """There is nothing much to do
        We are just shutting down the machine - ungracefully ...
        """
        self.shutdown()
        time.sleep(5) # Hack!

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

    def remove(self):
        '''
        Remove all files which were created during the VM creation.
        '''
        logger.debug("Removing host %s" % self.vm_name)
        self.destroy()
        self.remove_images()
        self.undefine()

    def boot(self):
        self._virsh("start %s" % self.vm_name)

    def reboot(self):
        self._virsh("reboot %s" % self.vm_name)

    def shutdown(self):
        self._virsh("shutdown %s" % self.vm_name)

    def destroy(self):
        self._virsh("destroy %s" % self.vm_name)

    def define(self, definition):
        with tempfile.NamedTemporaryFile() as f:
            logger.debug(f.name)
            f.write(definition)
            f.flush()
            self._virsh("define '%s'" % f.name)

    def undefine(self):
        self._virsh("undefine %s" % self.vm_name)

    def dumpxml(self):
        return self._virsh("dumpxml '%s'" % self.vm_name)


class NewVMHost(VMHost):
    '''A host which is actually a virtual guest.
    VMHosts are not much different from other hosts, besides that we can
    configure them.
    '''
    image_specs = None

    network_configuration = "network=default"
    disk_bus_type = "virtio"

    vm_prefix = "i-"
    description = "managed-by-igor"
    custom_install_args = None

    def __init__(self, name, image_specs):
        """
        Args
            name: The name of the VM, for newly created VMs this can contain
                  the variable {identifier}, which get's replaced by a unique
                  identifier upon creation. This is intended to prevent name
                  conflicts.
            image_specs: A list of ImageSpecs for disks to be created
        """
        super(NewVMHost, self).__init__(name)
        self.custom_install_args = {}
        self.image_specs = image_specs

    def prepare(self):
        logger.debug("Preparing a new VMHost")
        identifier = "%s%s" % (self.vm_prefix, self.session.cookie)
        self.vm_name = self.vm_name.format(identifier=identifier)
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
        logger.debug("Preparing vm: %s" % self.vm_name)

        # Sane defaults
        virtinstall_args = {
            "connect": "'%s'" % self.connection_uri,
            "name": "'%s'" % self.vm_name,
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

        virtinstall_args.update(self.custom_install_args)

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


class CommonLibvirtHostOrigin(igor.main.Origin):
    connection_uri = None
    storage_pool = None
    network_configuration = None

    def __init__(self, connection_uri, storage_pool, network_configuration):
        self.connection_uri = connection_uri
        self.storage_pool = storage_pool
        self.network_configuration = network_configuration

    def __set_host_props(self, host):
        host.connection_uri = self.connection_uri
        host.storage_pool = self.storage_pool
        host.network_configuration = self.network_configuration

    def _create_default_host(self):
        name = "default-{identifier}"
        host = NewVMHost(name=name, image_specs=[ \
                 VMImage("8G", [ \
                   igor.partition.Partition("pri", "1M", "1G") \
                 ]) \
               ])
        self.__set_host_props(host)

        return host

    def _use_existing_host(self, name):
        """Reuses a virtual guest and cond. removes it at the end

        Args:
            name: Name of the VM to be used
        """
        host = VMHost(name=name)
        self.__set_host_props(host)
        return host

    def items(self):
        return NotImplementedError


class CreateDomainHostOrigin(CommonLibvirtHostOrigin):
    def name(self):
        return "VMAlwaysCreateHostOrigin(%s)" % str(self.__dict__)

    def items(self):
        hosts = {"default-libvirt": self._create_default_host()}
        for key in hosts:
            hosts[key].origin = self
        return hosts


class ExistingDomainHostOrigin(CommonLibvirtHostOrigin):
    """Provides access to all existing g    uests
    """

    def name(self):
        return "VMExistingHostOrigin(%s)" % str(self.__dict__)

    def _list_domains(self):
        domains = []
        cmd = "list --all"
        domain_pattern = re.compile("\s*(\d+)\s+([\w-]+)\s+(\w+.*$)")
        txt = str(LibvirtConnection._virsh(cmd, self.connection_uri))
        for line in txt.split("\n"):
            match = domain_pattern.search(line)
            if match:
                domid, domname, state = match.groups()
                if state in ["running", "shut off"]:
                    domains.append(domname)
        return domains

    def items(self):
        domains = self._list_domains()
        logger.debug("Found the following existing domains: %s" % domains)
        hosts = {n: self._use_existing_host(n) for n in domains}
        for key in hosts:
            hosts[key].origin = self
        return hosts
