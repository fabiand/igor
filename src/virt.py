
import logging
import os
import subprocess
from string import Template

from adt import *
import gvfs
from gvfs import run

logger = logging.getLogger(__name__)

GVFS_IS_STILL_BROKEN = True
LOOP_IS_STILL_BROKEN = True

class VMImage(UpdateableObject):
    '''
    An image specififcation for a VMHost.
    This are actually params for truncate and parted.

    Parameters
    ----------
    size : int-like
        Size in GB
    label : string, optional
        label in ['gpt', 'mbr', 'loop']
    partitions : Array of Partitions
    '''
    filename = None
    size = 4
    label = "gpt"
    partitions = [{}]

    def __init__(self, size, partitions, label="gpt", filename=None):
        self.filename = filename
        self.size = size
        self.partitions = partitions
        self.label = label

    def create(self, session_dir="/tmp"):
        if self.filename is None:
            self.filename = run("mktemp --tmpdir='%s' 'vmimage-XXXX'" % \
                                session_dir)
        logger.debug("Creating VM image '%s'" % self.filename)
        self.truncate()
        self.partition()
        return self.filename

    def remove(self):
        logger.debug("Removing VM image '%s'" % self.filename)
        os.remove(self.filename)

    def truncate(self):
        run("truncate --size=%s '%s'" % (self.size, self.filename))

    def partition(self):
        for_parted = []

        # Create label
        if self.label not in ['gpt', 'mbr', 'loop']:
            raise Exception("No valid label given.")
        for_parted.append("mklabel %s" % self.label)

        # Create all partitions
        if self.partitions is None or len(self.partitions) is 0:
            logger.debug("No partitions given")
        else:
            for p in self.partitions:
                for_parted.append(p.for_parted())

        # Quit parted
        for_parted.append("quit")

        for parted_cmd in for_parted:
            run("parted '%s' '%s'" % (self.filename, parted_cmd))


class Partition(UpdateableObject):
    '''
    Params
    ------
    An array of dicts containing:
    - part_type (pri, sec, ext)
    - fs_type (ext[234], btrfs, ...), optional
    - start (see parted)
    - end (see parted)
    '''
    part_type = None
    start = None
    end = None
    fs_type = ""

    def __init__(self, pt, start, end, fst=""):
        self.part_type = pt
        self.start = start
        self.end = end
        self.fs_type = fst

    def for_parted(self):
        return "mkpart %s %s %s %s" % (self.part_type, self.fs_type, \
                                       self.start, self.end)


class VMHost(Host):
    session = None
    image_specs = None
    isofilename = None

    kernel_filename = None
    kernel_args = ""
    kernel_args_debug = "rdshell rdinitdebug"
    initrd_filename = None
    disk_images = []

    def prepare_profile(self, p):
        logger.debug("Preparing VMHost")
        assert (self.session is not None)
        self.prepare_images()
        self.prepare_vm()
        self.start_vm_and_install_os()

    def prepare_images(self):
        logger.debug("Preparing images")
        if self.image_specs is None or len(self.image_specs) is 0:
            logger.info("No image spec given.")
        else:
            for image_spec in self.image_specs:
                self.disk_images.append(image_spec.create(self.session.dirname))

    def prepare_vm(self):
        logger.debug("Preparing vm")
        tmp_kernel, tmp_initrd = self.extract_kernel_and_initrd()

        self.kernel_filename = os.path.join(self.session.dirname, "vmlinuz0")
        self.initrd_filename = os.path.join(self.session.dirname, "initrd0+iso.img")

        build_new_initrd_cmd = Template("""
{ cd $(dirname '${isofilename}') ; \
  echo "$(basename '${isofilename}')" | cpio -H newc --quiet -L -o ; \
} | gzip -9 | cat '${tmp_initrd}' - > "${initrd}"
""").safe_substitute( \
    isofilename=self.isofilename, \
    tmp_initrd=tmp_initrd, \
    initrd=self.initrd_filename)
        run(build_new_initrd_cmd)

    def start_vm_and_install_os(self):
        kernel_args = self.kernel_args
        kernel_args += " root=live:/%s rootfstype=auto ro liveimg check rootflags=loop" % os.path.basename(self.isofilename)
        kernel_args += self.kernel_args_debug

        kernel_args = " ".join(set(kernel_args.split(" ")))

        self.__qemukvm_start_vm_and_install_os(kernel_args)

    def __qemukvm_start_vm_and_install_os(self, kernel_args):
        cmd = Template("""
qemu-kvm \
    -name "${cookie}" \
    -m 512 -net user -net nic \
    -kernel "${kernel}" -initrd "${initrd}" -append "${kernel_args}" \
""").substitute(
    cookie=self.session.cookie, \
    kernel=self.kernel_filename, \
    initrd=self.initrd_filename, \
    kernel_args=kernel_args)

        for disk in self.disk_images:
            cmd += "    -drive file='%s',if=none,format=raw \n" % disk

        run(cmd)

    def __libvirt_start_vm_and_install_os(self, kernel_args):
        virtinstall = Template("""
virt-install \
    --name "vm-${cookie}" \
    --ram 512 \
    --boot kernel="${kernel}",initrd="${initrd}",kernel_args="${kernel_args}" \
""").substitute(
    cookie=self.session.cookie, \
    kernel=self.kernel_filename, \
    initrd=self.initrd_filename, \
    kernel_args=kernel_args)

        for disk in self.disk_images:
            virtinstall += "    --disk path='%s' \n" % disk

        run(virtinstall)

    def extract_kernel_and_initrd(self):
        files = []
        assert (self.isofilename is not None)
        if LOOP_IS_STILL_BROKEN and GVFS_IS_STILL_BROKEN:
            for fn in ["isolinux/vmlinuz0", "isolinux/initrd0.img"]:
                fn_dst = os.path.join(self.session.dirname, os.path.basename(fn))
                run("iso-read --image='%s' --extract='%s' --output-file='%s'" \
                    % (self.isofilename, fn, fn_dst))
                files.append(fn_dst)

        elif GVFS_IS_STILL_BROKEN is False:
            assert(False)
        elif LOOP_IS_STILL_BROKEN is False:
            with gvfs.LosetupMountedArchive(self.isofilename) as iso:
                logger.debug("Preparing libvirt machine (%s)" % iso.mountpoint)
                run("cd '%s' && cp 'isolinux/vmlinuz0' " + \
                    "'isolinux/initrd0.img' '%s'" % ( \
                        iso.mountpoint, self.session.dirname))
        else:
            debug.error("No other method to extract iso contents.")
        return files

    def remove_images(self):
        if self.image_specs is None or len(self.image_specs) is 0:
            logger.info("No image spec given.")
        else:
            for image_spec in self.image_specs:
                image_spec.remove()

    def remove_vm(self):
        pass

    def remove(self):
        self.remove_vm()
        self.remove_images()

    def submit_testsuite(self, session, testsuite):
        self.prepare_profile(testsuite.profile)

#( echo "rhev-hypervisor6-6.3-20120502.3.auto69.el6.devel.iso" \
# | cpio -H newc --quiet -L -o ) |   gzip -9 \
# | cat /home/fdeutsch/tmp/v/l/isolinux/initrd0.img - > ~/tmp/v/initrd0.img

# qemu-kvm -net user -m 2048 -kernel vmlinuz0 -initrd initrd0.img \
# -append "initrd=initrd0.img \
# root=live:/rhev-hypervisor6-6.3-20120502.3.auto69.el6.devel.iso \
# rootfstype=auto ro liveimg check rootflags=loop rdshell rdinitdebug \
# console=tty0"
