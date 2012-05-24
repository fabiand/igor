#/bin/bash

# The following env vars are available:
# TESTJOB           - original kernelarg
# TESTJOBURL        - the url where this script was fetched from
# TESTJOBBASEURL    - the api base
# TESTJOBSCRIPT     - this file

[[ -e /usr/libexec/ovirt-functions ]] &&
{
  . /usr/libexec/ovirt-functions
}

SESSION=${igor_cookie}
CURRENT_STEP=${igor_current_step}
TESTSUITE=${igor_testsuite}

env | sort

debug()
{
  echo $@ >&2
}
put_file()
{
  DST=$1
  FILENAME=$2
  curl --silent \
    --request PUT \
    --header "X-Igord-Session: $SESSION" \
    --header "X-Igord-Filename: $DST" \
    --upload-file "$FILENAME" \
    "$BASEURL/job/$SESSION/artifact"
}

api_call()
{
  P=$1
  COOKIE=$2
  URL="${TESTJOBBASEURL%/}/${P#/}"
  debug "Calling $P ($URL)"
  curl --silent "$URL"
#  [[ "x$COOKIE" != "x" ]] && ARGS="--header \"X-Igord-Session: $SESSION\" $ARGS"
}

get_kernelarg()
{
  KEY=${1:-testsuite}
  VALUE=$(egrep -o '$KEY=[^[:space:]]+' /proc/cmdline)
  return ${VALUE#$KEY=}
}

{
  set -v
  TMPDIR=$(mktemp -d /tmp/oat-XXXXX)
  cd $TMPDIR
  api_call testsuite/$TESTSUITE | tar xj

  for TESTCASE in testcases/*
  do
    chmod a+x $TESTCASE
    ./$TESTCASE
    RETVAL=$?

    # FIXME upload log

    if [[ $RETVAL = 0 ]];
    then
      api_call job/step/$SESSION/$CURRENT_STEP/success
    else
      api_call job/step/$SESSION/$CURRENT_STEP/failed
      exit 1
    fi
    CURRENT_STEP=$(($CURRENT_STEP + 1))
  done
}

exit 0

# vim: sw=2:
