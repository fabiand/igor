#!/bin/bash

# The following env vars are available:
# TESTJOB - original kernelarg
# APIURL  - the api base

#
# Vars
#
SESSION=${igor_cookie}
CURRENT_STEP=${igor_current_step}
TESTSUITE=${igor_testsuite}
TMPDIR=$(mktemp -d /tmp/oat.XXXXXX)
LOGFILE=${TMPDIR}/testsuite.log

# 
# Functions
#
debug() { echo "$SESSION $(date) - $@" >&2 ; }
debug_curl() { debug "Calling $1" ; curl --silent "$1" ; }
api_url() { echo "${APIURL%/}/${1#/}" ; }
api_call() { debug_curl $(api_url "$1") ; }
step_succeeded() { api_call jobs/$SESSION/step/$CURRENT_STEP/success ; }
step_failed()    { api_call jobs/$SESSION/step/$CURRENT_STEP/failed ; }
skip_step()      { api_call jobs/$SESSION/step/$CURRENT_STEP/skip ; }
step_result()    { api_call jobs/$SESSION/step/${1}/result ; }
add_artifact()
{
  local DST=$1
  local FILENAME=$2
  [[ -z $DST || -z $FILENAME ]] && {
    debug "Adding artifact: Destination '$DST' or filename '$FILENAME' missing." ; return 1 ;
  }
  debug "Adding artifact '$DST': '$FILENAME'"
  URL=$(api_url "jobs/$SESSION/artifacts/$DST")

  python <<EOP
import urllib2

filename = "$FILENAME"
url = "$URL"

data = open(filename, "rb").read()

opener = urllib2.build_opener(urllib2.HTTPHandler)
request = urllib2.Request(url, data=data)
request.add_header('Content-Type', 'text/plain')
request.get_method = lambda: 'PUT'
resp = opener.open(request)
EOP
}
testcase_x_succeeded_last_time() {
  # Go backwards and return 0 in the case that the
  # last run of X was successfull
  TESTCASENAME=$1
  debug "Checking dependency of testcase $TESTCASENAME"
  for N in $(seq $CURRENT_STEP -1 0)
  do
    if [[ -e $N-$TESTCASENAME ]]
    then
      if step_result $N | grep -qi true
      then
        debug "Dependency $N-$TESTCASENAME was met"
        return 0
      else
        debug "Dependency $N-$TESTCASENAME failed"
        return 1
      fi
    fi
  done
  debug "No such testcase: $N-$TESTCASENAME"
  return 2
}


#
# Run
#
{
  debug "Entering tmpdir $TMPDIR"
  cd $TMPDIR

  debug "Fetching testsuite '$TESTSUITE' for session '$SESSION'"
  api_call "jobs/$SESSION/testsuite" > testcases.tar.bz2
  tar imxf testcases.tar.bz2

  debug "Running testcases"
  cd testcases

  # FIXME bc
  export APIURL SESSION CURRENT_STEP TESTSUITE 

  for TESTCASE in $(ls -1 . | sort -n)
  do
    [[ -d $TESTCASE ]] && {
      debug "Is not testcase, a directory: $TESTCASE" ; continue
    }

    # Skip testcases we already ran through
    TESTCASESTEP=${TESTCASE/-*/}
    [[ $TESTCASESTEP -lt $CURRENT_STEP ]] && {
      debug "Skipping testcase $TESTCASE (already run)" ; continue
    }

    # Skip a testcase if a dependency failed
    TESTCASEDEPS=$TESTCASE.deps
    [[ -e $TESTCASEDEPS ]] && {
      debug "Checking testcase dependencies for step $CURRENT_STEP"
      DEPENDENCIES_MET=true
      cat $TESTCASEDEPS | while read DEP;
      do
        debug "  Checking state of dependency '$DEP'"
        testcase_x_succeeded_last_time "$DEP" || DEPENDENCIES_MET=false
      done

      $DEPENDENCIES_MET || {
        skip_step
        debug "Skipping testcase $TESTCASE (dependency failed)" ; continue
      }
    }

    RETVAL=4242
    TESTCASELOGFILE=${TMPDIR}/$TESTCASE.log
    :> $TESTCASELOGFILE
    debug "Running testcase $TESTCASE"
    {
      export IGOR_APIURL=$APIURL
      export IGOR_SESSION=$SESSION
      export IGOR_CURRENT_STEP=$CURRENT_STEP
      export IGOR_TESTSUITE=$TESTSUITE
      export IGOR_LIBDIR="$PWD/lib/"
      export PYTHONPATH="$IGOR_LIBDIR:$PYTHONPATH" # For convenience
      chmod a+x $TESTCASE
      ./$TESTCASE
      RETVAL=$?
    } > $TESTCASELOGFILE 2>&1
    debug "Testcase ended with: $RETVAL"
    [ -s $TESTCASELOGFILE ] && add_artifact "${TESTCASE#*-}.log" $TESTCASELOGFILE

    if [[ $RETVAL == 0 ]];
    then
      step_succeeded > /dev/null
    else
      add_artifact "log" $TESTCASELOGFILE
      step_failed > /dev/null
      # We are not breaking here, because a failed testcase could be expected
    fi

    if [[ -e "/tmp/quit-testing" ]];
    then
      debug "Quitting testing on request"
      break
    fi

    # Check if we are continuing
    api_call jobs/$SESSION/status | grep '"state":' | grep -q '"running"' || {
      debug "Testsuite is not running anymore"
      break
    }

    CURRENT_STEP=$(($CURRENT_STEP + 1))
  done

  if [[ -e "/tmp/reboot-requested" ]]
  then
    debug "Got request to initiate reboot"
    { sleep 5 ; reboot ; } &
  fi

  # Add a summary
  api_call jobs/$SESSION/status > "/tmp/job_status.json"
  add_artifact "job_status.json.txt" "/tmp/job_status.json"
} 2>&1 | tee $LOGFILE

add_artifact "testsuite.log" $LOGFILE

debug "Done"

# vim: sw=2:
