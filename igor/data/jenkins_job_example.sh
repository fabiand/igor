#!/bin/bash -xe
#
# Example script for jenkins
#
# Pass the following env vars (explanantions, examples and jenkins
# snippet below):
# APIURL
# IGORCLIENTURL
# TESTPLAN
# PROFILENAME

# Examples for the required env vars (whcih can be defined by/within Jenkins):
#
# APIURL - The URL where we can reach Igord
#          By default Igord is launched on port 8080 and listening on all
#          interfaces
# APIURL="http://igor.example.com:8080/"
#
# IGORCLIENTURL - The URL where we can fetch the latest igorclient tool
#                 (deployed with igor)
# IGORCLIENTURL="${APIURL}static/data/igorclient.sh"
#
# TESTPLAN - The testplan which shall be run
# TESTPLAN="ai_basic"
#
# ISONAME - This ISO is used to create the profile PROFILENAME, if it
#           does not exist already
#           OPTIONAL: Only needed if profile $PROFILENAME does not exist
# ISONAME=$(ls *.edited.iso)
#
# PROFILENAME - The name of an existing or to be created profile
#               There are two ways how this PROFILENAME is used:
#               Igor checks if this profile exists:
#               (a) It exists: Igor is using the existsing profile
#               (b) It does not exist: Igor creates the profile using
#                   the given ISO (ISONAME)
# PROFILENAME="fdeutsch-$ISONAME"


# A Jenkins shell snippet could look like:
# Assumptions: SELECTED_TESTPLAN is a build parameter
#              An ISO was created by a previous job containing the igor-client
# <code>
# export APIURL="http://igor.example.com:8080/"
# export IGORCLIENTURL="${APIURL}static/data/igorclient.sh"
# export TESTPLAN="${SELECTED_TESTPLAN:-ai_basic}"   
#
# export ISONAME=$(ls *.edited.iso)    # Grab the iso of the previous jenkins job
# export PROFILENAME="fdeutsch-$ISONAME"
#
# curl --silent -O "${APIURL}static/data/jenkins_job_example.sh"
# bash -x "jenkins_job_example.sh"
# </code>


[[ -z $IGORCLIENTURL ]] && exit 1
[[ -z $APIURL ]] && exit 1

[[ -z $TESTPLAN ]] && exit 1
[[ -z $PROFILENAME ]] && exit 1


# REPORT_EMAIL_TO
# REPORT_EMAIL_FROM
# ISONAME

pyc() { python -c "$@" ; }
highlight() { pyc "txt=\"$1\"; r='-' * len(txt); print(\"%s\n%s\n%s\" % (r, txt, r));" ; }


highlight "Fetching igor client from server"
    curl --silent "${IGORCLIENTURL}" --output "igorclient.sh"
    [[ -e igorclient.sh ]]

CREATE_PROFILE=true
if $(bash ./igorclient.sh profiles | grep -q "\"$PROFILENAME\"")
then
    highlight "Profile '$PROFILENAME' exists, reusing this."
    CREATE_PROFILE=false
else
    highlight "Profile '$PROFILENAME' does not exists, creating new one."
fi

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
    ADDITIONAL_KARGS=" local_boot_trigger=${APIURL}testjob/{igor_cookie}"
    bash ./igorclient.sh add_profile_from_iso "$PROFILENAME" "$ISONAME" "$ADDITIONAL_KARGS"
}


highlight "Create igor jobs by running the testplan '$TESTPLAN'"
    bash ./igorclient.sh testplan_submit "$TESTPLAN" "tbd_profile=$PROFILENAME"
    highlight "Wait for the testplan to finish"
    bash ./igorclient.sh wait_testplan $TESTPLAN

PASSED=$(bash ./igorclient.sh testplan_status $TESTPLAN | grep passed | tail -n1 | egrep -o "true|false")

highlight "Getting artifacts archive"
    bash ./igorclient.sh testplan_report $TESTPLAN > report.rst.txt
    bash ./igorclient.sh testplan_report $TESTPLAN junit > junit-report.xml
    bash ./igorclient.sh testplan_artifacts_and_reports $TESTPLAN


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
