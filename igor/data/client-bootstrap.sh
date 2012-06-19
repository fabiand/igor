#!/bin/bash -e

# The following env vars are available:
# TESTJOB - original kernelarg
# APIURL  - the api base

#
# Vars
#
SESSION=${igor_cookie}
CURRENT_STEP=${igor_current_step}
TESTSUITE=${igor_testsuite}
TMPDIR=$(mktemp -d)
LOGFILE=${TMPDIR}/testcases.log

# 
# Functions
#
debug() { echo "$SESSION $(date) - $@" >&2 ; }
debug_curl() { debug "Calling $1" ; curl --silent "$1" ; }
api_url() { echo "${APIURL%/}/${1#/}" ; }
api_call() { debug_curl $(api_url "$1") ; }
step_succeeded() { api_call job/step/$SESSION/$CURRENT_STEP/success ; }
step_failed()    { api_call job/step/$SESSION/$CURRENT_STEP/failed ; }
add_artifact()
{
  local DST=$1
  local FILENAME=$2
  [[ -z $DST || -z $FILENAME ]] && {
    debug "Adding artifact: Destination '$DST' or filename '$FILENAME' missing." ; return 1 ;
  }
  debug "Adding artifact '$DST': '$FILENAME'"
  URL=$(api_url "job/artifact/for/$SESSION/$DST")
  curl --silent --request PUT --upload-file - "$URL" <"$FILENAME"
}



#
# Run
#
{
  [[ -e /usr/libexec/ovirt-functions ]] &&
  {
    debug "Loading oVirt functions"
    . /usr/libexec/ovirt-functions
    debug "Loading defaults"
    . /etc/default/ovirt
  }

  debug "Entering tmpdir $TMPDIR"
  cd $TMPDIR

  debug "Fetching testsuite '$TESTSUITE' for session '$SESSION'"
  api_call "job/testsuite/for/$SESSION" > testcases.tar.bz2
  tar imxf testcases.tar.bz2

  debug "Running testcases"
  cd testcases

  typeset -fx debug debug_curl
  typeset -fx api_url api_call add_artifact
  typeset -fx step_succeeded step_failed
  export APIURL SESSION CURRENT_STEP TESTSUITE

  for TESTCASE in $(ls -1 . | sort -n)
  do
    [[ -d $TESTCASE ]] && {
      debug "Is not testcase, a directory: $TESTCASE" ; continue
    }

    TESTCASESTEP=${TESTCASE/-*/}
    [[ $TESTCASESTEP -lt $CURRENT_STEP ]] && {
      debug "Skipping testcase $TESTCASE" ; continue
    }

    debug "Running testcase $TESTCASE"
    {
      chmod a+x $TESTCASE
      ./$TESTCASE
      RETVAL=$?
    }
    debug "Testcase ended with: $RETVAL"

    if [[ $RETVAL == 0 ]];
    then
      step_succeeded
    else
      step_failed
      # We are not breaking here, because a failed testcase could be expected
    fi

    # Check if we are continuing
    api_call job/status/$SESSION | grep '"state":' | grep -q '"running"' || {
      debug "Testsuite is not running anymore"
      break
    }

    CURRENT_STEP=$(($CURRENT_STEP + 1))
  done

  # Add a summary
  api_call job/status/$SESSION > "/tmp/job_status.json"
  add_artifact "job_status.json.txt" "/tmp/job_status.json"
} 2>&1 | tee $LOGFILE

add_artifact "testcases.log" $LOGFILE

debug "Done"

# vim: sw=2:
