#!/bin/bash

. /usr/libexec/ovirt-functions

# Reply before we reboot, otherwise this won't work
add_artifact "ovirt.log" "/var/log/ovirt.log"
step_succeeded
reboot


exit 0
