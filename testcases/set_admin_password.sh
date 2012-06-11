#!/bin/bash

#
# Set the admin password to PW
#
PW="ovirt"


main ()
{
    . /usr/libexec/ovirt-functions

    unmount_config /etc/passwd /etc/shadow
    echo -n $PW | passwd --stdin admin

    return 0
}

main

exit $?
