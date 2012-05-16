#!/bin/env python
# -*- coding: utf-8 -*-

from testing import *
from virt import *
import cobbler

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

        host = VMHost(session=session, \
                    image_specs=image_specs)

        host.prepare_profile(profile)
#        host.submit_testsuite(session, testsuite)

        logger.debug(session.artifacts())

        c = cobbler.Cobbler("http://127.0.0.1:25151/")
        cs = c.new_session()
        cs.add_system(host._vm_name, host.get_first_mac_address(), "rhevh-6.3-ai22")

        host.boot()
