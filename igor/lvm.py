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

from utils import run

logger = logging.getLogger(__name__)


class PhysicalVolume(object):
    image = None
    uuid = None

    def __init__(self, image):
        self.image = image

    def create(self):
        if not os.path.exists(self.image):
            raise Exception("Backing image does not exist: %s" % self.image)
        with self.losetup() as losetup:
            dev = losetup.device
            run("pvcreate -ff -y -v '%s'" % dev)
            self.uuid = run("pvs --noheadings -o uuid '%s'" % dev)
            logger.debug("PV with UUID %s created on %s" %
                         (self.uuid, self.image))

    def losetup(self):
        return Losetup(self.image)


class VolumeGroup(object):
    name = None
    pvs = None
    uuid = None

    def __init__(self, name, pvs):
        self.name = name
        self.pvs = pvs

    def create_pvs(self):
        first_pv = None
        for pv in self.pvs:
            pv.create()
            if first_pv is None:
                first_pv = pv
        return first_pv

    def create(self):
        first_pv = self.create_pvs()

        with first_pv.losetup() as losetup:
            dev = losetup.device
            vg_cmd = "vgcreate -v '%s' '%s'" % (self.name, dev)
            run(vg_cmd)
            self.uuid = run("vgs --noheadings -o uuid '%s'" % self.name)
            logger.debug("VG with UUID %s created" % self.uuid)

        with self.losetup() as losetups:
            for (pv, losetup) in losetups.losetups.items():
                if pv is first_pv:
                    continue
                vg_cmd = "vgextend -v '%s' '%s'" % (self.name, losetup.device)
                run(vg_cmd)
                logger.debug("VG with UUID %s extended with PV %s" %
                             (self.uuid, self.name))

    def losetup(self):
        class VGMultiLosetup(MultiLosetup):
            vg = None

            def __init__(self, vg):
                self.vg = vg
                MultiLosetup.__init__(self, [(pv, pv.image)
                                             for pv in self.vg.pvs])

            def __enter__(self):
                MultiLosetup.__enter__(self)
                run("vgchange -v --available y '%s'" % self.vg.name)
                return self

            def __exit__(self, type, value, traceback):
                run("sync ; vgchange -v --available n '%s'" % self.vg.name)
                MultiLosetup.__exit__(self, type, value, traceback)
        return VGMultiLosetup(self)

    def scan_lvs(self):
        str_lvs = run("lvs --noheadings -o vg_name,lv_name,lv_path " +
                      "--separator '|'")
        infos = parse_lvm(str_lvs, "|", ["vg_name", "name", "path"])
        lvs = {}
        for info in infos:
            if info["vg_name"] == self.name:
                lvs[info["name"]] = {
                    "device": info["path"]
                }
        return lvs


class LogicalVolume(object):
    name = None
    vg = None
    size = None

    def __init__(self, name, vg, size):
        self.name = name
        self.vg = vg
        self.size = size

    def create(self):
        self.vg.create()

        with self.vg.losetup():
            vg_cmd = ("lvcreate -v -L '%s' -n '%s' '%s'" %
                      (self.size, self.name, self.vg.name))
            run(vg_cmd)

    def losetup(self):
        class LvLosetup(Losetup):
            lv = None
            device = None
            vg_losetup = None

            def __init__(self, lv):
                self.lv = lv
                self.vg_losetup = self.lv.vg.losetup()

            def __enter__(self):
                self.vg_losetup.__enter__()
                lvs = self.lv.vg.scan_lvs()
                print lvs
                if self.lv.name not in lvs:
                    raise Exception("LV not in VG")
                self.lv.device = lvs[self.lv.name]["device"]
                return self

            def __exit__(self, type, value, traceback):
                self.vg_losetup.__exit__(type, value, traceback)
        return LvLosetup(self)


def parse_lvm(text, separator="|", options=None):
#    """Rudimentary LVM out parsing
#    >>> text = "  /dev/loop0|k7hrQX-tCOr-RFev-nmnj-y1eQ-P0Ol-aaXbeH\n"
#    >>> text += "  /dev/loop1|x278B5-WU0J-kS35-YpKW-36eM-6cgV-WFPSlv"
#    >>> parse_lvm(text, "|")
#    [['/dev/loop0', 'k7hrQX-tCOr-RFev-nmnj-y1eQ-P0Ol-aaXbeH'],
#     ['/dev/loop1', 'x278B5-WU0J-kS35-YpKW-36eM-6cgV-WFPSlv']]
#    >>> parse_lvm(text, "|", ["name", "uuid"])
#    [{'name': '/dev/loop0', 'uuid': 'k7hrQX-tCOr-RFev-nmnj-y1eQ-P0Ol-aaXbeH'},
#     {'name': '/dev/loop1', 'uuid': 'x278B5-WU0J-kS35-YpKW-36eM-6cgV-WFPSlv'}]
#    """
    lst = []
    for line in text.split("\n"):
        line = line.strip()
        if line == "":
            continue
        tokens = line.split(separator)
        if options is None:
            lst.append(tokens)
        else:
            lst.append(dict(zip(options, tokens)))
    return lst


class Losetup:
    image = None
    device = None

    def __init__(self, image):
        self.image = image

    def __enter__(self):
        logger.debug("Setting up: %s" % self.image)
        _txt_devices = run(("losetup -v -f '%s'" +
                            " | egrep -o 'is /dev/loop[0-9]+'") % self.image)
        devices = str(_txt_devices).split(" ")
        self.device = devices[1]
        logger.debug("losetup: %s on %s" % (self.image, self.device))
        return self

    def __exit__(self, type, value, traceback):
        run("sync ; losetup -d '%s'" % self.device)
        self.device = None


class MultiLosetup(object):
    images = None
    losetups = None

    def __init__(self, kimages):
        self.images = dict(kimages)
        self.losetups = {}

    def __enter__(self):
        for key, image in self.images.items():
            self.losetups[key] = Losetup(image)
            self.losetups[key].__enter__()
        return self

    def __exit__(self, type, value, traceback):
        for key, image in self.images.items():
            self.losetups[key].__exit__(type, value, traceback)
            self.losetups[key] = None

if __name__ == "__main__":
    run("rm a.img ; truncate -s 2G a.img")
    run("rm b.img ; truncate -s 2G b.img")
    pvs = [PhysicalVolume("a.img"),
           PhysicalVolume("b.img")]
    vg = VolumeGroup("abc", pvs)
    lv = LogicalVolume("abc-lv", vg, "1G")
    lv.create()

    logger.info("Testing")
    with lv.losetup() as losetup:
        print(run("pvs ; vgs ; lvs --noheadings -o name,path"))
