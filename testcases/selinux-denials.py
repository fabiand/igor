#!/bin/env python
# vim:set sw=2:

import sys
import re

AUDITLOG = "/var/log/audit/audit.log"

comm_regex = re.compile("comm=\"([^\"]+)\"")

def get_denials():
  denials = []
  comms = set([])
  with open(AUDITLOG, "r") as f:
    for line in f:
      if line.startswith("type=AVC") and "denied" in line:
        denials.append(line.strip())
        comms.add(comm_regex.search(line).groups()[0])
  return denials, comms

def main():
  denials, comms = get_denials()
  if len(denials) > 0:
    sys.stderr.write("The following comms lead to denials:\n - %s\n" % \
                                                          "\n - ".join(comms))
    sys.stderr.write("Denials: \n" + "\n - ".join(denials))
    return 1
  return 0

if __name__ == '__main__':
  retval = main()
  sys.exit(retval)
