#!/bin/bash -xe
#
# Example script for jenkins
#
# Pass the following env vars:

[[ -z $IGORCLIENTURL ]] && exit 1
[[ -z $APIURL ]] && exit 1

[[ -z $TESTPLAN ]] && exit 1
[[ -z $PROFILENAME ]] && exit 1


# REPORT_EMAIL_TO
# REPORT_EMAIL_FROM
# ISONAME

pyc() { python -c "$@" ; }
highlight() { pyc "r='-' * len(\"$1\"); print(r + \"\n$@\n\" + r);" ; }


highlight "Fetching igor client from server"
    curl --silent "${IGORCLIENTURL}" --output "igorclient.sh"
    [[ -e igorclient.sh ]]

CREATE_PROFILE=true
bash ./igorclient.sh profiles | grep -q "\"$PROFILENAME\"" && {
    highlight "Profile '$PROFILENAME' exists, reusing this."
    CREATE_PROFILE=false
} || {
    highlight "Profile '$PROFILENAME' does not exists, creating new one."
}

$CREATE_PROFILE && {
    # This is an artifact from a previous job
    ISONAME=${ISONAME:-$(ls *.iso | tail -n1)}
    highlight "Using ISO '$ISONAME'"

    [[ $(ls *.iso | wc -l) -gt 1 ]] && {
        echo More than one iso ;
        ls *.iso ;
    }

    [[ -e $ISONAME ]]

    highlight "Create cobbler distro and profile by uploading the kernel and initrd image and kargs from '$ISONAME'"
    sudo livecd-iso-to-pxeboot "$ISONAME"
    KERNEL=vmlinuz0
    INITRD=initrd0.img
    KARGS=kargs
    # Get the default kargs from the isolinux cfg and remove some kargs to not exceed the 256 chars limit of pxelinux
    echo $(sed -n "/APPEND/s/[[:space:]]*APPEND//p" tftpboot/pxelinux.cfg/default \
           | egrep -o "(root|ro|live|check|rhgb|quiet|rd)[^[:space:]]*") > $KARGS
    echo " local_boot_trigger=${APIURL}testjob/{igor_cookie}" >> $KARGS
    ln tftpboot/$KERNEL $KERNEL
    ln tftpboot/$INITRD $INITRD
    bash ./igorclient.sh add_profile "$PROFILENAME" "$KERNEL" "$INITRD" "$KARGS"
    sudo rm -rvf tftpboot kargs
}


highlight "Create igor jobs by running the testplan '$TESTPLAN'"
    bash ./igorclient.sh testplan_submit "$TESTPLAN" "tbd_profile=$PROFILENAME"
    highlight "Wait for the testplan to finish"
    bash ./igorclient.sh wait_testplan $TESTPLAN

PASSED=$(bash ./igorclient.sh testplan_status $TESTPLAN | grep passed | tail -n1 | egrep -o "true|false")

highlight "Getting artifacts archive"
    bash ./igorclient.sh testplan_report $TESTPLAN > report.rst.txt
    bash ./igorclient.sh testplan_report $TESTPLAN junit > junit-report.xml
    #bash ./igorclient.sh testplan_artifacts_and_reports $TESTPLAN


$CREATE_PROFILE && {
    highlight "remove cobbler distro/profile"
    bash ./igorclient.sh remove_profile "$PROFILENAME"
}

# Passed? The exit.
[[ "x$PASSED" == "xtrue" ]] && exit 0

# Not passed. Send a mail.
[[ ! -z $REPORT_EMAIL_TO && ! -z $REPORT_EMAIL_FROM ]] && {
    mail -s "[Igor Report ] Job $IGORCOOKIE: $LAST_STATE" \
         -r "$REPORT_EMAIL_FROM" \
         -a $ARTIFACTSARCHIVE \
         "$REPORT_EMAIL_TO" < igor-report.txt
}
exit 1
