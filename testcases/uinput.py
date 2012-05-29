#!/bin/env python

import sys
import os

def main():
    TESTCASEFILENAME=sys.args[0]
    UINPUTPYDIR="%s.d/uinputpy/build/lib.linux-x86_64-2.7/" % TESTCASEFILENAME

    sys.path.append(UINPUTPYDIR)

def enter():
    pass
    # uinput keys

def capture():
    pass
    # setterm -dump $N
    # cat /dev/vcs$N
    # cat /dev/vcsa$N

if __name__ == "__main__":
    main()
