#!/bin/bash -xe
#
# Example script for jenkins
#
# Pass the following env vars:

[[ -z $IGORCLIENTURL ]] && exit 1
[[ -z $APIURL ]] && exit 1
[[ -z $BASENAMEPREFIX ]] && exit 1
[[ -z $ARTIFACTSARCHIVE ]] && exit 1
[[ -z $JENKINS_PROJECT_NAME ]] && exit 1
[[ -z $BUILD_TAG ]] && exit 1

pyc() { python -c "$@" ; }
drawline() { pyc "print('$2' * $1);" ; }
highlight() { L=$(drawline ${#1} -) ; echo -e "\n$L\n$@\n$L\n" ; }

# This is an artifact from a previous job
ISONAME=$(ls *.iso | tail -n1)
highlight "Using ISO '$ISONAME'"

[[ $(ls *.iso | wc -l) -gt 1 ]] && { 
    echo More than one iso ; 
    ls *.iso ;
}

highlight "Fetching igor client"
curl -v "${IGORCLIENTURL}" --output "igorclient.sh"
[[ -e igorclient.sh ]]

export BASENAME="${BASENAMEPREFIX}${BUILD_TAG}"       # profile and distro name are derived from BASENAME
export PROFILENAME="$BASENAME-profile"

highlight "Create cobbler distro and profile"
bash ./igorclient.sh extra_profile_add "$BASENAME" "${JENKINS_PROJECT_NAME}/lastSuccessfulBuild/artifact/$ISONAME"

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

highlight "remove cobbler distro/profile"
bash ./igorclient.sh extra_profile_remove "$BASENAME"

[[ "x$LAST_STATE" == "xpassed" ]] && exit 0

exit 1
