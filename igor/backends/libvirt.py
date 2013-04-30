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

from igor.partition import DiskImage, Partition
from igor.utils import run, dict_to_args
from lxml import etree
import igor.main
import igor.partition
import logging
import os
import re
import shutil
import subprocess
import tempfile


logger = logging.getLogger(__name__)


def initialize_origins(category, CONFIG):
    origins = []

    __con_args = (CONFIG["libvirtd.connection_uri"],
                  CONFIG["libvirtd.virt-install.storage_pool"],
                  CONFIG["libvirtd.virt-install.network_configuration"])

    if category == "host":
        origins += [("libvirt-create",
                      CreateDomainHostOrigin(*__con_args)),
                     ("libvirt-existing",
                      ExistingDomainHostOrigin(*__con_args))]

    if category == "profile":
        origins += [("libvirt",
                     ProfileOrigin(*__con_args))]

    return origins


class VMImage(igor.partition.Layout):
    def compress(self, dst_fmt="qcow2"):
        '''Convert the raw image into a qemu image.
        '''
        assert dst_fmt in ["raw", "qcow2"], "Only qcow2 and raw allowed"

        dst_filename = "%s.%s" % (self.filename, dst_fmt)
        cmd = ("nice time qemu-img convert -c -O %s '%s' '%s'" %
               (dst_fmt, self.filename, dst_filename))
        run(cmd)
        cmd = "mv '%s' '%s'" % (dst_filename, self.filename)
        run(cmd)
        self.format = dst_fmt


class LibvirtConnection(object):
    connection_uri = None
    poolname = "default"

    def __init__(self, connection_uri):
        self.connection_uri = connection_uri

    def virsh(self, cmd):
        return LibvirtConnection._virsh(cmd, self.connection_uri)

    @staticmethod
    def _virsh(cmd, connection_uri):
        return run("LC_ALL=C virsh --connect='%s' %s" % (connection_uri, cmd))

    def volume_list(self):
        data = self.virsh("vol-list --pool " +
                          "'{pool}'".format(pool=self.poolname))
        assert data

        vols = []
        for line in unicode(data).strip().split("\n")[2:]:
            vol, path = re.split("\s+", line, 1)
            vols.append(vol)
        return vols

    def create_volume(self, image, volname=None):
        """Create a volume on the server side and populate it

        Args:
            image: VMMImage to be uploaded and created
            volname: (optional) name of the new volume

        Returns:
            The pool/volname on the server side
        """
        if not DiskImage in type(image).mro():
            raise RuntimeError("Unknown type: %s" % image)
        disk = image.filename
        volname = volname or os.path.basename(disk)
        poolvol = "%s/%s" % (self.poolname, volname)
        if volname not in self.volume_list():
            logger.debug("Creating volume")
            self.virsh(("vol-create-as --name '%s' --capacity '%s' " +
                        "--format '%s' --pool '%s'") %
                       (volname, image.size, image.format, self.poolname))
        logger.debug("Uploading disk image '%s' to volume '%s'" %
                     (disk, poolvol))
        self.upload_volume(volname, disk)
        return poolvol

    def upload_volume(self, volname, filename):
        """Upload a file to a volume

        Args:
            volanme: Name of the volume on the server side
            filename: Filename of the local file to be uploaded
        """
        self.virsh(("vol-upload --vol '{vol}' --file '{file}' " +
                    "--pool '{pool}'").format(vol=volname,
                                              file=filename,
                                              pool=self.poolname))

    def delete_volume(self, volname):
        """Delete a volume on the server side

        Args:
            volname: Volume to be deleted
        """
        self.virsh("vol-delete --vol " +
                   "'{vol}' --pool '{pool}'".format(pool=self.poolname,
                                                    vol=volname))

    def volume_path(self, volname):
        """Return the FS path 8server side) for the volume

        Args:
            volname: The name of the volume
        Returns:
            The absolute pathname for the folume on the server
        """
        return self.virsh(("vol-path --pool '{pool}' " +
                           "{vol}").format(pool=self.poolname,
                                           vol=volname))


class VMHost(igor.main.Host):
    """Corresponds to a libvirt domain.
    This class can be used to control the domain and wrap it to provide
    the igor Host API.
    """

    vm_name = None
    connection_uri = "qemu:///system"
    poolname = "default"

    remove_afterwards = True

    _connection = None

    def __init__(self, name, remove=True):
        super(VMHost, self).__init__()
        self.vm_name = name
        self.remove_afterwards = remove
        self._connection = LibvirtConnection(self.connection_uri)

    def _virsh(self, cmd):
        return self._connection.virsh(cmd)

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

    def __get_cdrom_target_name(self):
        path = ("/domain/devices/disk[@device='cdrom']/target/@dev")
        dom = etree.XML(self.dumpxml())
        targets = dom.xpath(path)
        return sorted(targets)[0]

    def change_cdrom_source(self, volname):
        """Set the <source file='...' /> of the first device which is a cdrom
        """
        target = self.__get_cdrom_target_name()
        if volname:
            filename = self._connection.volume_path(volname)
            cmd = "change-media --domain %s --path %s --source %s --force" % \
                (self.vm_name, target, filename)
        else:
            # Eject otherwise
            cmd = "change-media --domain %s --path %s --eject --force" % \
                (self.vm_name, target)
        self._virsh(cmd)

    def prepare(self):
        """There is nothing much to do
        We are just shutting down the machine - ungracefully ...
        """
        self.destroy()  # Kill the machine!

    def purge(self):
        if self.remove_afterwards:
            self.remove()
        else:
            logger.debug("VMHost shall not be removed at the end.")

    def remove_images(self):
        for image in self.get_disk_images():
            volname = os.path.basename(image)
            self._connection.delete_volume(volname)

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

    def __eq__(self, other):
        """Override to allow simple comparisons
        >>> a = VMHost("foo")
        >>> b = VMHost("foo")
        >>> a == b
        True
        >>> b = VMHost("bar")
        >>> a == b
        False
        >>> pool = [a, b]
        >>> VMHost("foo") in pool
        True
        >>> VMHost("baz") in pool
        False
        >>> VMHost("foo") in set(pool)
        True
        """
        return self.get_name() == other.get_name()

    def __hash__(self):
        """Override to allow "in" opertor on collections
        >>> a = VMHost("foo")
        >>> b = VMHost("bar")

        >>> VMHost("foo") in [a, b]
        True
        >>> VMHost("baz") in [a, b]
        False

        >>> VMHost("foo") in set([a, b])
        True
        >>> VMHost("baz") in set([a, b])
        False
        """
        return hash(self.get_name())


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
            "boot": "cdrom,network,hd",
            "disk": "device=cdrom,bus=ide,format=raw,path=/dev/null",
            "network": self.network_configuration,
            "graphics": "spice",
            "video": "vga",
            "channel": "spicevmc",
            "noautoconsole": None,      # Prevents opening a window
            "import": None,
            "dry-run": None,
            "print-xml": None,
            "force": None
        }

        virtinstall_args.update(self.custom_install_args)

        cmd = "virt-install "
        cmd += dict_to_args(virtinstall_args)

        for image_spec in self.image_specs:
            assert type(image_spec) is VMImage
            image_spec.compress()
            poolvol = self._connection.create_volume(image_spec)
            cmd += (" --disk vol=%s,device=disk,bus=%s,format=%s" %
                    (poolvol, self.disk_bus_type, image_spec.format))

        definition = run(cmd)

        self.define(definition)

    def remove_images(self):
        # Remove or local images (created initially)
        if self.image_specs is None or len(self.image_specs) is 0:
            logger.info("No image spec given.")
        else:
            for image_spec in self.image_specs:
                image_spec.remove()
        # Now also remove the remote volumes
        super(NewVMHost, self).remove_images()


class CommonLibvirtOrigin(igor.main.Origin):
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
        image_specs = [VMImage("8G", [Partition("pri", "1M", "1G")])]
        host = NewVMHost(name=name, image_specs=image_specs)
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


class CreateDomainHostOrigin(CommonLibvirtOrigin):
    def name(self):
        return "VMAlwaysCreateHostOrigin(%s)" % str(self.__dict__)

    def items(self):
        hosts = {"default-libvirt": self._create_default_host()}
        for key in hosts:
            hosts[key].origin = self
        return hosts


class ExistingDomainHostOrigin(CommonLibvirtOrigin):
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


class LibvirtProfile(igor.main.Profile):
    """A kernel, initrd + kargs
    A libvirt profile is actually just a dict with kernel,initrd and kargs
    Assigning happens by populating the domain definition with this values
    """

    origin = None

    name = None

    # FIXME
    _datadir_prefix = "/var/tmp/igor"
    _datadir = None
    _boot_iso = None

    __isolinux_bin = "/usr/share/syslinux/isolinux.bin"

    values = {"kernel": None,
              "initrd": None,
              "cmdline": None}

    __previous_values = {}

    __host = None
    __additional_kargs = None

    _volname = None

    def __init__(self, name):
        self.name = name
        self._datadir = os.path.join(self._datadir_prefix, self.name)
        if not os.path.isdir(self._datadir):
            os.makedirs(self._datadir)

        self._root_dir = os.path.join(self._datadir, "iso_root")
        self._isolinux_dir = os.path.join(self._root_dir, "isolinux")

        self._boot_iso = os.path.join(self._datadir, "boot.iso")

        self.__created_files = []
        super(LibvirtProfile, self).__init__()

    def get_name(self):
        return self.name

    def assign_to(self, host, additional_kargs=""):
        assert VMHost in host.__class__.mro()

        self.__host = host
        self.__additional_kargs = additional_kargs

        self._volname = "%s-boot" % self.get_name()
        self.__mkiso(additional_kargs)
        self.__host.change_cdrom_source(self._volname)

    def revoke_from(self, host):
        assert self.__host == host
        try:
            self.__host.change_cdrom_source(None)
        except etree.XMLSyntaxError:
            logger.debug("Can' revoke profile from %s, might be deleted." %
                         host)

    def kargs(self, kargs):
        """get or set kargs
        """
        self.__mkiso(kargs)

    def enable_pxe(self, host, enable):
        if enable:
            self.assign_to(host, self.__additional_kargs)
        else:
            self.revoke_from(host)

    def delete(self):
        for filename in self.__created_files:
            logger.debug("Removing %s" % filename)
            os.remove(filename)
        self.__created_files = []
        self.__host._connection.delete_volume(self._volname)

    def populate_with(self, kernel_file, initrd_file, kargs_file):
        self.__prepare_iso_root(kernel_file, initrd_file, kargs_file)

    def __prepare_iso_root(self, kernel_file, initrd_file, cmdline_file):
        # Dir containing the ISO contents
        if not os.path.isdir(self._root_dir):
            os.mkdir(self._root_dir)

        # Subdir containing isolinux+kernel stuff
        if not os.path.isdir(self._isolinux_dir):
            os.mkdir(self._isolinux_dir)

        # Copy isolinux
        isolinuxbin_dst = os.path.join(self._isolinux_dir,
                                       os.path.basename(self.__isolinux_bin))
        logger.debug("Copying %s -> %s" % (self.__isolinux_bin,
                                           isolinuxbin_dst))
        shutil.copyfile(self.__isolinux_bin, isolinuxbin_dst)

        # Copy kernel+initrd
        files = {"kernel": kernel_file, "initrd": initrd_file,
                 "cmdline": cmdline_file}
        for component in files.keys():
            srcfilename = files[component]
            dstfile = os.path.join(self._isolinux_dir, component)
            logger.debug("Copying %s -> %s" % (srcfilename, dstfile))
            shutil.copyfile(srcfilename, dstfile)
            self.__created_files += [dstfile]

    def __mkiso(self, additional_kargs):
        """This is a hack as long as igor doesn't use isos directly
        http://www.syslinux.org/wiki/index.php/ISOLINUX
        """
        assert self.__host

        cmdlinefile = os.path.join(self._isolinux_dir, "cmdline")

        with open(cmdlinefile) as cmdline:
            kargs = cmdline.read().strip()
        logger.debug("Read kargs: %s" % kargs)
        logger.debug("Additional kargs: %s" % additional_kargs)

        cookie = self.__host.session.cookie
        appendline = " ".join(kargs.split() + additional_kargs.split())
        appendline = appendline.format(igor_cookie=cookie)

        # Create isolinux.cfg
        isolinuxcfgdata = "\n".join(["default {name}",
                                     "label {name}",
                                     "    kernel kernel",
                                     "    initrd initrd",
                                     "    append {kargs}"])

        # Write config
        isolinuxcfg = os.path.join(self._isolinux_dir, "isolinux.cfg")
        with open(isolinuxcfg, "w") as cfg:
            data = isolinuxcfgdata.format(name=self.name,
                                          kargs=appendline)
            cfg.write(data)

        cmd = ["mkisofs",
               "-output", self._boot_iso,
               "-no-emul-boot",
               "-eltorito-boot", "isolinux/isolinux.bin",
               "-eltorito-catalog", "isolinux/boot.cat",
               "-boot-load-size", "4",
               "-boot-info-table",
               self._root_dir]

        subprocess.check_output(cmd)

        image = DiskImage(self._boot_iso, "256M", "raw")
        self.__host._connection.create_volume(image, self._volname)
        return self._volname


class ProfileOrigin(CommonLibvirtOrigin):
    """Origin for libvirt profiles
    """

    __profiles = None

    def __init__(self, *args, **kwargs):
        super(ProfileOrigin, self).__init__(*args, **kwargs)
        self.__profiles = []

    def name(self):
        return "libvirt origin FIXME"

    def items(self):
        """Retrieve all available profiles
        """
        logger.debug("Retrieving all libvirt profile items: %s" %
                     self.__profiles)
        items = {}
        for p in self.__profiles:
            items[p.get_name()] = p
        return items

    def create_item(self, pname, kernel_file, initrd_file, kargs_file):
        logger.debug("Creating libvirt profile: %s" % pname)
        profile = LibvirtProfile(pname)
        profile.populate_with(kernel_file, initrd_file, kargs_file)
        self.__profiles.append(profile)
        logger.debug("Created libvirt profile: %s" % profile)
