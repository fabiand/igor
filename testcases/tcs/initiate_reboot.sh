#!/bin/bash

#
# Rebooting consist of two parts: initiating and confirming the reboot
#

. ${IGOR_LIBDIR}/lib/common/common.sh

main()
{
    . /usr/libexec/ovirt-functions

    # Add an ertifact, just in case
    igor_add_artifact "ovirt.log" "/var/log/ovirt.log"

    # Reply before we reboot, otherwise our reply will get lost, as it would be
    # issued after we call for a reboot
    igor_step_succeeded

    reboot
}


main

sleep 60
# Should not be reached as we want to block until we reboot

exit 0
