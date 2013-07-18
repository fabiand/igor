#!/bin/bash -xe
#
# Example script for the commandline
#

pyc() { python -c "$@" ; }
drawline() { pyc "print('$2' * $1);" ; }
highlight() { L=$(drawline ${#1} -) ; echo -e "\n$L\n$@\n$L\n" ; }

usage()
{
    cat <<EOM
Usage: $0 <iso>
Additional optional env avrs:
APIURL
TESTSUITE
PROFILENAME
HOST
EOM
}

ISONAME=$1
TESTSUITE=${TESTSUITE:-example}
PROFILENAME=${PROFILENAME:-profileForIso}
HOST=${HOST:-some_vm}                   # Ignored currently


highlight "Using ISO '$ISONAME'"

[[ -e $ISONAME ]] || {
    echo "ISO does not exist"
    exit 1
}


highlight "Create cobbler distro and profile by uploading the ISO '$ISONAME'"
bash ./igorclient.sh extra_profile_add "$BASENAME" "$ISONAME"
highlight "The ISO was uploadded and a profile created."

highlight "Now submit an igor job"
bash ./igorclient.sh submit "$TESTSUITE" "$PROFILENAME" "$HOST"

export $(bash ./igorclient.sh cookie)
[[ -z $IGORCOOKIE ]] && {
    echo "Got no Igor cookie. What went wrong?"
    exit 2
}

highlight "The job is starting and waited to reach some endstate"
bash ./igorclient.sh start
bash ./igorclient.sh wait_state "aborted|failed|timedout|passed"
highlight "The job has finished"

LAST_STATE=$(bash ./igorclient.sh state)

highlight "Downloading the artifacts into $ARTIFACTSARCHIVE"
bash ./igorclient.sh artifacts $ARTIFACTSARCHIVE

#bash ./igorclient.sh status
#bash ./igorclient.sh report

highlight "At last: Remove cobbler distro and profile"
bash ./igorclient.sh extra_profile_remove "$BASENAME"

