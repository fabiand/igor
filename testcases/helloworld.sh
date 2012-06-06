#!/bin/bash -e
# vim: set sw=2:

# Change into "our" directory tree
cd "${0}.d"

main()
{
  source mylib.sh
  echo "Hello World."
  pwd
  ls -lah
}

main

exit 0
