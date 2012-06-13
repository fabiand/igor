#!/bin/bash -xe

#
# This snippet can be used within jenkins as the snippet used 
# for a custom job
#

export APIURL="http://igor.example.com:8080/"
export IGORCLIENTURL="${APIURL}static/data/igorclient.sh"
export BASENAMEPREFIX="igor-"
export ARTIFACTSARCHIVE="testsuite-artifacts.tar.bz2"
export JENKINS_PROJECT_NAME="node-devel"
export REPORT_EMAIL_FROM="igord-node@ovirt.org"
export REPORT_EMAIL_TO="fabiand@example.com"
export BUILD_TAG

JJOB="jenkins_job.sh"

# Get the fully-fledged Jenkins script
curl --silent "${APIURL}static/data/jenkins_job_example.sh" -o $JJOB

# If it exists, run it
[[ -e $JJOB ]]
bash -xe $JJOB

# Clean up and extract artifacts for a better access
rm -vf *.iso *.sh

tar xvf testsuite-artifacts.tar.bz2
