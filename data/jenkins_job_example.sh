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

# This is an artifact from a previous job
ISONAME=$(ls *.iso | tail -n1)
[[ $(ls *.iso | wc -l) -gt 1 ]] && { 
    echo More than one iso ; 
    ls *.iso ;
}

echo Using ISO '$ISONAME'

wget "${IGORCLIENTURL}" -O "igorclient.sh"
[[ -e igorclient.sh ]]

export BASENAME="${BASENAMEPREFIX}${BUILD_TAG}"       # profile and distro name are derived from BASENAME
export PROFILENAME="$BASENAME-profile"

# Create cobbler distro and profile
bash ./igorclient.sh extra_profile_add "$BASENAME" "$ISONAME"

# Create igor job
bash ./igorclient.sh submit example "$PROFILENAME" ahost
export $(bash ./igorclient.sh cookie)
[[ -z $IGORCOOKIE ]] && { echo No Igor cookie ; return 1 ; }
# ... start and wait to reach some endstate
bash ./igorclient.sh start
bash ./igorclient.sh wait_state "aborted|failed|timedout|done"

LAST_STATE=$(bash ./igorclient.sh state)

# get artifacts archive
bash ./igorclient.sh artifacts $ARTIFACTSARCHIVE
bash ./igorclient.sh status

# remove job
bash ./igorclient.sh end

# remove cobbler distro/profile
bash ./igorclient.sh extra_profile_remove "$BASENAME"

[[ "x$LAST_STATE_SUCCESS" == "xdone" ]] || exit 1

exit 0
