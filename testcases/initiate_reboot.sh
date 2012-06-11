#!/bin/bash

#
# Rebooting consist of two parts: initiating and confirming the reboot
#

main()
{
    . /usr/libexec/ovirt-functions

    # Add an ertifact, just in case
    add_artifact "ovirt.log" "/var/log/ovirt.log"

    # Reply before we reboot, otherwise our reply will get lost, as it would be
    # issued after we call for a reboot
    step_succeeded

    reboot
}


main

sleep 60
# Should not be reached as we want to block until we reboot

exit 0
