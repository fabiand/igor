#!/bin/bash -e
# vim: set sw=2:

# This is a example to illustrate the usage

. ${IGOR_LIBDIR}/lib/common/common.sh

main()
{
  # This exampel has an attached folder, so change into "our" directory tree
  # This is not mandatory but why else should we provide our own dir?
  cd "${0}.d"

  # Now source my own lib
  source mylib.sh

  # This will appear in the logs attached to the calling service
  echo "Hello World."
  pwd
  ls -lah

  igor_debug "Hello World 2"

  # This will push "/var/log/ovirt.log" to the server as the artifacts "ovirt.log"
  igor_add_artifact "ovirt.log" "/var/log/ovirt.log"
}

main

# If this testcase succeeds, return 0, otherwise something else
exit 0
