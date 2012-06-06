#!/bin/env python
# -*- coding: utf-8 -*
# vim: set sw=2:

import sys
import os
import logging

logger = logging.getLogger(__name__)
logging.basicConfig( \
    format='%(levelname)s - %(module)s - %(asctime)s - %(message)s', \
    level=logging.DEBUG)

def main():
  UINPUTPYDIR="uinputpy/build/lib.linux-x86_64-2.7/"
  sys.path.append(UINPUTPYDIR)

  pairs = [("abc", "def")]
  for inp, outp in pairs:
    send_input(inp)
    logger.debug(capture_and_expect(outp) == True)

def send_input(txt):
  logger.debug("Inputing: %s" % txt)
  # …

def capture_and_expect(expr):
  logger.debug("Capturing: %s" % expr)
  # setterm -dump $N
  # cat /dev/vcs$N
  # cat /dev/vcsa$N

if __name__ == "__main__":
  logger.debug("Starting")
  main()
