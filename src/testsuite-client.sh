#/bin/bash

# The following env vars are available:
# TESTJOB - original kernelarg
# APIURL  - the api base


SESSION=${igor_cookie}
CURRENT_STEP=${igor_current_step}
TESTSUITE=${igor_testsuite}

debug() { echo "$SESSION $(date) - $@" >&2 ; }

[[ -e /usr/libexec/ovirt-functions ]] &&
{
  debug "Loading oVirt functions"
  . /usr/libexec/ovirt-functions
}

debug "Environment variables:"
env | sort

debug "Args:"
echo $@

debug "Defining functions"
api_url()
{
  echo "${APIURL%/}/${1#/}"
}

api_call()
{
  URL=$(api_url "$1")
  COOKIE=$2
  debug "Calling $P ($URL)"
  curl --silent "$URL"
#  [[ "x$COOKIE" != "x" ]] && ARGS="--header \"X-Igord-Session: $SESSION\" $ARGS"
}

add_artifact()
{
  debug "Adding artifact '$DST': '$FILENAME'"
  DST=$1
  FILENAME=$2
  URL=$(api_url "job/artifact/for/$SESSION/$DST")
  curl --silent --request PUT --upload-file "$FILENAME" "$URL"
}

step_succeeded()
{
  api_call job/step/$SESSION/$CURRENT_STEP/success
}

step_failed()
{
  api_call job/step/$SESSION/$CURRENT_STEP/success
}

get_kernelarg()
{
  KEY=${1:-testsuite}
  VALUE=$(egrep -o '$KEY=[^[:space:]]+' /proc/cmdline)
  return ${VALUE#$KEY=}
}

main()
{
  debug "Fetching testsuite '$TESTSUITE' for session '$SESSION'"
  TMPDIR=$(mktemp -d /tmp/oat-XXXXX)
  cd $TMPDIR
  api_call "job/testsuite/for/$SESSION" | tar xj

  debug "Running testcases"
  cd testcases

  typeset -fx api_url api_call add_artifact
  typeset -fx step_succeeded step_failed
  export SESSION CURRENT_STEP TESTSUITE

  for TESTCASE in *
  do
    TESTCASESTEP=${TESTCASE/-*/}
    [[ $TESTCASESTEP -lt $CURRENT_STEP ]] && {
      debug "Skipping testcase $TESTCASE"
      continue
    }
    debug "Running testcase $TESTCASE"

    chmod a+x $TESTCASE
    ./$TESTCASE
    RETVAL=$?

    add_artifact "ovirt.log" "/var/log/ovirt.log"

    if [[ $RETVAL = 0 ]];
    then
      api_call job/step/$SESSION/$CURRENT_STEP/success
    else
      api_call job/step/$SESSION/$CURRENT_STEP/failed
      exit 1
    fi
    CURRENT_STEP=$(($CURRENT_STEP + 1))
  done
  debug "Finished testcases"
  debug "Finished testsuite $TESTSUITE"
}

main

# vim: sw=2:
