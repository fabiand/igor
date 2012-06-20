#!/bin/env python
# -*- coding: utf-8 -*
# vim: set sw=2:

import sys
import os
import logging
import time
import re
import random

sys.path.append(os.environ["IGOR_LIBDIR"])
import common.common as common

UINPUTPYDIR=os.path.join(common.igor.libdir, "uinput/dst/lib64/python2.7/site-packages/")
sys.path.append(UINPUTPYDIR)
import uinput


logger = logging.getLogger(__name__)

def main():
  pairs = [("HHH  Hel\tl\no", "def")]
  for inp, outp in pairs:
    send_input(inp)
    logger.debug(capture_and_expect(outp) == True)

def all_keys():
  keys = []
  for k in uinput.__dict__:
    if re.match("^KEY_", k):
      keys.append(uinput.__dict__[k])
  return keys

device = uinput.Device(all_keys())

def send_input(txt):
  logger.debug("Inputing: %s" % txt)
  for char in txt:
    if char.isupper():
      device.emit(uinput.KEY_LEFTSHIFT, 1)
    press_key(char_to_key(char))
    if char.isupper():
      device.emit(uinput.KEY_LEFTSHIFT, 0)

def char_to_key(char):
  kmap = {
    " ": "space",
    "\t": "tab",
    "\n": "enter"
  }
  if char in kmap:
    char = kmap[char]
  key_key = "KEY_%s" % char.upper()
  return uinput.__dict__[key_key]

def press_key(key, delay=12):
  device.emit(key, 1)
  time.sleep(1.0/100*delay * random.uniform(0.5,1.5))q
  device.emit(key, 0)

def capture_and_expect(expr):
  logger.debug("Capturing: %s" % expr)
  # setterm -dump $N
  # cat /dev/vcs$N
  # cat /dev/vcsa$N

if __name__ == "__main__":
  logger.debug("Starting")
  main()
