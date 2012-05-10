#!/bin/env python
# -*- coding: utf-8 -*-

from adt import *
from virt import *

logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    testcases = [ \
        Testcase(name="first", source="Hi there")
    ]

    testsuite = Testsuite(name="simple", \
                          testcases=testcases)
    profile=Profile(kernel_args="firstboot")

    with TestSession(cleanup=False) as session:
        image_specs = [
            VMImage("1G", [ \
                Partition("pri", "1M", "1G")
            ])
        ]

#        iso="rhev-hypervisor6-6.3-20120509.1.auto323.el6.iso"
        iso="ovirt-node-iso-2.3.0-1.builder.fc16.iso"
        host = VMHost(session=session, \
                    image_specs=image_specs, \
                    isofilename="/home/fdeutsch/Downloads/" + iso)

        host.prepare_profile(profile)
#        host.submit_testsuite(session, testsuite)

        logger.debug(session.artifacts())

        c = Cobbler("http://127.0.0.1:25151/")
        c.add_system(host._vm_name, host.get_first_mac_address(), "rhevh-6.3-ai22")

        host.boot()
