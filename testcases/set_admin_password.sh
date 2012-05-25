#!/bin/bash

. /usr/libexec/ovirt-functions

PW="ovirt"

unmount_config /etc/passwd /etc/shadow
echo -n $PW | passwd --stdin admin

exit 0
