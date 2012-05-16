#!/bin/env python
# -*- coding: utf-8 -*-

import time

from testing import *
from virt import *
from cobbler import Cobbler
from job import *
from utils import run

logging.basicConfig(level=logging.DEBUG)

testsets = [Testset("aset", [ \
    Testcase(name="first", source="""
#!/bin/bash

echo "Hello Node."

""")
])]

testsuite = Testsuite(name="simple", \
                      testsets=testsets)

host = VMHost(name="8g-gpt-1g", image_specs=[
                  VMImage("8G", [ \
                      Partition("pri", "1M", "1G")
                  ])
              ])

cobbler = Cobbler("http://127.0.0.1:25151/")
kargs = "BOOTIF=eth0 storage_init firstboot local_boot_trigger=http://192.168.122.1:8080/firstboot/${igor_cookie} adminpw=%s" % run("openssl passwd -salt OMG 123123")
profile = cobbler.new_profile("rhevh-6.3-ai22", kargs)

if __name__ == "__main__":
    jc = JobCenter()

    resp = jc.submit_testsuite(testsuite, profile, host)
    jc.run_next_job()

    logger.info("Giving some time to do something ...")
    time.sleep(30)

#    jc.end_current_job()
