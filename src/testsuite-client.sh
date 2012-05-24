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
  ARGS="--silent \"${TESTJOBBASEURL%/}/${P#/}\""
  [[ "x$COOKIE" != "x" ]] && ARGS="--header \"X-Igord-Session: $SESSION\" $ARGS"
  echo curl $ARGS
  curl $ARGS
}

get_kernelarg()
{
  KEY=${1:-testsuite}
  VALUE=$(egrep -o '$KEY=[^[:space:]]+' /proc/cmdline)
  return ${VALUE#$KEY=}
}


#api_call /jobs
api_call "/job/step/$SESSION/0/success"

#echo Args: $@
echo Provided: $SESSION $CURRENT_STEP
#echo $TESTJOB $TESTJOBURL $TESTJOBBASEURL $TESTJOBSCRIPT
#put_file passwd /etc/passwd

#unmount_config /etc/passwd /etc/shadow
#echo -n "123123" | passwd --stdin admin


exit 0

# vim: sw=2:
