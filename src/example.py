#!/bin/env python
# -*- coding: utf-8 -*-

from testing import *
from virt import *
from cobbler import Cobbler
from job import *

logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    testcases = [ \
        Testcase(name="first", source="Hi there")
    ]

    testsuite = Testsuite(name="simple", \
                          testcases=testcases)

    cobbler = Cobbler("http://127.0.0.1:25151/")
    profile = cobbler.new_profile("rhevh-6.3-ai22")

    host = VMHost(image_specs=[
                      VMImage("1G", [ \
                          Partition("pri", "1M", "1G")
                      ])
                  ])

    hosts = [host]

    js = JobCenter()

    js.submit_testsuite(testsuite, profile, hosts)
    js.run_next_job()
