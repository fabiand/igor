#!/bin/bash -xe
#
# Example script for jenkins
#
# Pass the following env vars:

[[ -z $IGORCLIENTURL ]] && exit 1
[[ -z $APIURL ]] && exit 1
[[ -z $BASENAMEPREFIX ]] && exit 1
[[ -z $ARTIFACTSARCHIVE ]] && exit 1
[[ -z $BUILD_TAG ]] && exit 1
# $REPORT_EMAIL_TO
# $REPORT_EMAIL_FROM
# ISONAME

pyc() { python -c "$@" ; }
drawline() { pyc "print('$2' * $1);" ; }
highlight() { L=$(drawline ${#1} -) ; echo -e "\n$L\n$@\n$L\n" ; }

# This is an artifact from a previous job
ISONAME=${ISONAME:-$(ls *.iso | tail -n1)}
highlight "Using ISO '$ISONAME'"

[[ $(ls *.iso | wc -l) -gt 1 ]] && { 
    echo More than one iso ; 
    ls *.iso ;
}

[[ -e $ISONAME ]]

highlight "Fetching igor client from server"
curl "${IGORCLIENTURL}" --output "igorclient.sh"
[[ -e igorclient.sh ]]

export BASENAME="${BASENAMEPREFIX}${BUILD_TAG}"       # profile and distro name later are derived from this BASENAME
export PROFILENAME="$BASENAME-profile"                # future profile name will be BASENAME-profile

highlight "Create cobbler distro and profile by uploading the ISO '$ISONAME'"
bash ./igorclient.sh extra_profile_add "$BASENAME" "$ISONAME"

highlight "Create igor job"
bash ./igorclient.sh submit example "$PROFILENAME" ahost
export $(bash ./igorclient.sh cookie)
[[ -z $IGORCOOKIE ]] && { echo No Igor cookie ; return 1 ; }
highlight "... start and wait to reach some endstate"
bash ./igorclient.sh start
bash ./igorclient.sh wait_state "aborted|failed|timedout|passed"

LAST_STATE=$(bash ./igorclient.sh state)

highlight "get artifacts archive"
bash ./igorclient.sh artifacts $ARTIFACTSARCHIVE
bash ./igorclient.sh status

bash ./igorclient.sh report | tee igor-report.rst

highlight "remove cobbler distro/profile"
bash ./igorclient.sh extra_profile_remove "$BASENAME"

# Passed? The exit.
[[ "x$LAST_STATE" == "xpassed" ]] && exit 0

# Not passed. Send a mail.
[[ ! -z $REPORT_EMAIL_TO && ! -z $REPORT_EMAIL_FROM ]] && {
    mail -s "[Igor Report ] Job $IGORCOOKIE: $LAST_STATE" \
         -r "$REPORT_EMAIL_FROM" \
         -a $ARTIFACTSARCHIVE \
         "$REPORT_EMAIL_TO" < igor-report.rst
}
exit 1
