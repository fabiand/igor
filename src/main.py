#!/bin/env python

from adt import *
from virt import *

logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    testcases = [ \
        Testcase(name="first", source="Hi there")
    ]

    testsuite = Testsuite(name="simple", \
                          profile=Profile(kernel_args="firstboot"), \
                          testcases=testcases)


    with TestSession(cleanup=False) as session:
        image_specs = [
            VMImage("1G", [ \
                Partition("pri", "1M", "1G")
            ])
        ]

        host = VMHost(session=session, \
                    image_specs=image_specs, \
                    isofilename="/home/fdeutsch/Downloads/rhev-hypervisor6-6.3-20120502.3.auto307.el6.iso")

        host.submit_testsuite(session, testsuite)

        logger.debug(session.artifacts())

