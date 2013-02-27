#!/bin/bash

IGORCOOKIEFILE=~/.igorcookie
DEBUG=${DEBUG:-true}

export FUNC_USAGE=""

#
# Common functions
#
debug() { [[ -z $DEBUG ]] || echo "${IGORCOOKIE:-(no session)} $(date) - $@" >&2 ; }
error() { echo -e "\n$@\n" >&2 ; }
die() { error $@ ; echo -e "Usage: $FUNC_USAGE\n" ; exit 1 ; }

pyc() { echo -e "$@" | python ; }

help() # This help
{
  echo -e "\nUsage: $0 FUNCTION [<params>, ...]\n\nFUNCTION:"
  grep "[[:alnum:]]() #" $0 | sort | sed "s/#/\t/ ; s/()//" | awk -F "\t" '{ printf "%-33s %-40s\n", $1, $2}'

}

_is_command() { help | egrep -q "^$1[[:space:]]" ; }

_filter_key() { grep "\"$1\":" | tr -d '":,' | egrep -o "$1 [^[:space:]]+" | cut -d' ' -f 2 ; }

has_cookie() 
{
  [[ -e $IGORCOOKIEFILE ]] && {
    . $IGORCOOKIEFILE
    debug "Using cookie $IGORCOOKIE"
  }
  [[ -z $IGORCOOKIE ]] && {
  echo "Please use '$0 cookie <IGORCOOKIE>' to set the current session."
  exit 1
  }
}

_api_url()
{
  echo ${APIURL:-http://localhost:8080/}${1#/}
}

api()
{
  URL=$(_api_url $1)
  debug "Calling $URL"
  curl --silent "$URL"
  echo ""
}

_py_urlencode()
{
  pyc "import urllib as u; print u.urlencode($@);"
}

view() # View the source of function FUNCNAME
{
  FUNC_USAGE="$0 $FUNCNAME <FUNCNAME>"
  [[ -z $1 ]] && die "FUNCNAME is mandatory."
  typeset -f $1
}

check() # Check the syntax of this script
{
  bash -n $0
}


#
# API stateless functions
#
jobs() # List all jobs
{
  api jobs
}

submit() # Submit a new job, e.g. submit <testsuite> <profile> <host>
{
  FUNC_USAGE="$0 $FUNCNAME <TESTSUITE> <PROFILE> <HOST> [<KARGS>]"
  TESTSUITE=$1
  PROFILE=$2
  HOST=$3
  KARGS=$4
  [[ -z $TESTSUITE ]] && die "Testsuitename is mandatory."
  [[ -z $PROFILE ]] && die "Profilename is mandatory."
  [[ -z $HOST ]] && die "Hostname is mandatory."

  TMPFILE=$(mktemp)
  URL="jobs/submit/$TESTSUITE/with/$PROFILE/on/$HOST"
  [[ -z $KARGS ]] || {
    QUERY=$(_py_urlencode "{'additional_kargs': '$KARGS'}")
    URL="$URL?$QUERY"
  }
  URL=$(_api_url $URL)
  debug "Calling $URL"
  curl --silent $URL | tee $TMPFILE
  cookie $(cat $TMPFILE | _filter_key cookie)
  rm -f $TMPFILE
}

cookie() # Get/Set the current job cookie
{
  [[ -z $1 ]] && {
    [[ -e $IGORCOOKIEFILE ]] && {
      cat $IGORCOOKIEFILE
    } || exit 1
  } || {
    IGORCOOKIE=$1
    echo IGORCOOKIE=$IGORCOOKIE > $IGORCOOKIEFILE
    debug "Setting cookie to $IGORCOOKIE"
  }
}

uncookie() # Remove current cookie
{
  rm -f $IGORCOOKIEFILE
  unset IGORCOOKIE
  debug "Removed current cookie"
}


#
# API statefull functions
#
abort() # Abort the current job
{
  has_cookie
  api jobs/$IGORCOOKIE/abort
  uncookie
}


start() # Start the current job
{
  has_cookie
  api jobs/$IGORCOOKIE/start
}

status() # Get the status of the current job
{
  has_cookie
  api jobs/$IGORCOOKIE/status
}

report() # Get the rst report
{
  has_cookie
  api jobs/$IGORCOOKIE/report
}

testsuite() # Get the testsuite for the current job
{
  ARCHIVE=${1:-testsuite.tar.bz2}
  FUNC_USAGE="$0 $FUNCNAME [<DSTARCHIVE=$ARCHIVE>]"
  has_cookie
  api /jobs/$IGORCOOKIE/testsuite > $ARCHIVE
}

artifacts() # Get all artifacts for the current job
{
  ARCHIVE=${1:-artifacts.tar.bz2}
  FUNC_USAGE="$0 $FUNCNAME [<DSTARCHIVE=$ARCHIVE>]"
  has_cookie
  api jobs/$IGORCOOKIE/artifacts/download > $ARCHIVE
}

testsuites() # List all available testsuites
{
  api testsuites
}

hosts() # List all available hosts
{
  api hosts
}

profiles() # List all available profiles
{
  api profiles
}

add_profile() # Add a profile from kernel, initrd and kargs files
{
  FUNC_USAGE="$0 $FUNCNAME <PROFILENAME> <KERNELFILE> <INITRDFILE> <KARGSFILE>"
  PNAME=$1
  KERNEL=$2
  INITRD=$3
  KARGS=$4
  [[ -z $PNAME ]] && die "Profile name is mandatory."
  [[ ! -e $KERNEL ]] && die "kernel file does not exist."
  [[ ! -e $INITRD ]] && die "initrd file does not exist."
  [[ ! -e $KARGS ]] && die "kargs file does not exist."
  grep -q "initrd=" $KARGS && {
    error "Removing initrd from $KARGS, use profile_kargs() to force"
    sed -i "s/initrd=[^[:space:]]*//" "$KARGS"
    error "Now using: $(cat $KARGS)"
  }
  grep -q "testjob" $KARGS || {
    die "'testjob' url missing in kargs $KARGS"
  }

  ARCHIVE="/tmp/${PNAME}_files.tar"
  debug "Creating '$ARCHIVE' with kernel, initrd and kargs"
  # Use transform to strip all leading paths
  tar --create --transform="s#^.*/##" --file="$ARCHIVE" $KERNEL $INITRD $KARGS

  URL=$(_api_url profiles/$PNAME)
  debug "Putting $ARCHIVE to $URL"
  curl --header "x-kernel-filename: $(basename $KERNEL)" \
       --header "x-initrd-filename: $(basename $INITRD)" \
       --header "x-kargs-filename: $(basename $KARGS)" \
       --upload-file $ARCHIVE "$URL"

  rm -f $ARCHIVE
# Slow:  curl -F "kernel=@$KERNEL" -F"initrd=@$INITRD" -F"kargs=@$KARGS" "$URL"
}

remove_profile() # Remove a profile
{
  FUNC_USAGE="$0 $FUNCNAME <PROFILENAME>"
  PNAME=$1
  [[ -z $PNAME ]] && die "Profile name is mandatory."
  debug "Removing profile '$PNAME'"
  api /profiles/$PNAME/remove
}

profile_kargs() # Set the kernel arguments of a profile
{
  FUNC_USAGE="$0 $FUNCNAME <PROFILENAME> <KARGS>"
  PNAME=$1
  KARGS=$2
  [[ -z $PNAME ]] && die "Profile name is mandatory."
  [[ -z $KARGS ]] && die "kargs are mandatory."
  URL=$(_api_url profiles/$PNAME)
  debug "Updating '$PNAME' kargs to: $KARGS"
  curl --data "kargs=$KARGS" "$URL"
}

testplan_submit() # Submit a testplan to be run, optional a query param with substitutions in the form of "var=val"
{
  FUNC_USAGE="$0 $FUNCNAME <TESTPLANNAME> [<SUBSTITUTIONS>]"
  PNAME=$1
  KARGS=$2
  [[ -z $PNAME ]] && die "Testplan name is mandatory."
  QUERY=""

  [[ -z $KARGS ]] || {
    QUERY="?$KARGS"
  }

  debug "Submitting testplan '$PNAME' with query '$QUERY'"
  api /testplans/$PNAME/submit$QUERY
}

testplan_status() # Status of a testplan
{
  FUNC_USAGE="$0 $FUNCNAME <TESTPLANNAME>"
  PNAME=$1
  [[ -z $PNAME ]] && die "Testplan name is mandatory."

  api /testplans/$PNAME/status
}

testplan_report() # Report of a testplan
{
  FUNC_USAGE="$0 $FUNCNAME <TESTPLANNAME> [junit]"
  PNAME=$1
  TYPE=$2
  [[ -z $PNAME ]] && die "Testplan name is mandatory."
  [[ -z $TYPE ]] || {
    TYPE=/$TYPE
  }

  api /testplans/$PNAME/report$TYPE
}

testplan_abort() # Abort a running testplan to be run
{
  FUNC_USAGE="$0 $FUNCNAME <TESTPLANNAME>"
  PNAME=$1
  [[ -z $PNAME ]] && die "Testplan name is mandatory."
  api /testplans/$PNAME/abort
}

#
# Convenience functions
#
state() # Just get the value of the status key
{
  has_cookie
  api jobs/$IGORCOOKIE/status | _filter_key state
}

testplan_state() # Just get the value of the testplan status key
{
  FUNC_USAGE="$0 $FUNCNAME <TESTPLANNAME>"
  PNAME=$1
  api /testplans/$PNAME | grep "state" | tail -n1 | _filter_key state
}

wait_state() # Wait until a job reaced a specific state (regex)
{
  EXPR=$1
  INTERVAL=${2:-10}
  STATE=""
  has_cookie
  echo -n "Waiting "
  export DEBUG=""
  TIME_START=$(date +%s)
  TIMEOUT=$(api jobs/$IGORCOOKIE/status | grep timeout | tail -n1 | _filter_key timeout)
  TIMEOUT=$(( $TIMEOUT * 2 )) # Higher timeout, because it can take time before the job ist actually started
  while true
  do
    STATE=$(state)
    echo $STATE | egrep -q "$EXPR" && break
    sleep $INTERVAL
    echo -n "."
    RUNTIME=$(( $(date +%s) - $TIME_START ))
    [[ $RUNTIME -gt $TIMEOUT ]] && {
      echo "Timed out ($TIMEOUT)"
      break;
    }
  done
  echo ""
  echo "Reached state '$(state)' ($STATE)"
  DEBUG=true
  return 0
}

wait_testplan() # Wait until a testplan ended
{
  FUNC_USAGE="$0 $FUNCNAME <TESTPLANNAME>"
  PNAME=$1
  INTERVAL=${2:-10}
  STATE=""
  echo -n "Waiting "
  export DEBUG=""
  while true
  do
    STATE=$(api testplans/$PNAME/status | grep status | tail -n1 | _filter_key status)
    echo $STATE | egrep -q "stopped" && break
    sleep $INTERVAL
    echo -n "."
  done
  echo ""
  echo "Reached state $STATE"
  DEBUG=true
  return 0
}

testplan_artifacts_and_reports() # Get all artifacts and reports related to a testplan
{
  FUNC_USAGE="$0 $FUNCNAME <TESTPLANNAME>"
  PNAME=$1
  NO=1
  for ID in $(api testplans/$PNAME | grep '"id"' | _filter_key id)
  do
    IGORCOOKIE=$ID artifacts "artifacts-for-$NO-$ID.tar.bz2"
    IGORCOOKIE=$ID report > "report-for-$NO-$ID.rst.txt"
    NO=$(($NO + 1))
  done
}

abort_all() # Abort all jobs
{
  jobs | _filter_key id | while read IGORCOOKIE
  do
    debug "Aborting $IGORCOOKIE"
    abort
  done
}

add_profile_from_iso() # Add a new profile from a livecd iso <isofilename>
{
  FUNC_USAGE="$0 $FUNCNAME <PROFILENAME> <ISONAME> [<ADDITIONAL_KARGS>]"
  PROFILENAME=$1
  ISONAME=$2
  ADDITIONAL_KARGS=$3
  # " local_boot_trigger=${APIURL}testjob/{igor_cookie}"
  [[ -z $PROFILENAME ]] && die "Profilename name is mandatory."
  [[ -z $ISONAME ]] && die "Isoname name is mandatory."
  debug "Extracting livecd"
  sudo livecd-iso-to-pxeboot "$ISONAME"
  KERNEL=vmlinuz0
  INITRD=initrd0.img
  KARGS=kargs
  # Get the default kargs from the isolinux cfg and remove some kargs to not exceed the 256 chars limit of pxelinux
  echo $(sed -n "/APPEND/s/[[:space:]]*APPEND//p" tftpboot/pxelinux.cfg/default \
         | egrep -o "(root|ro|live|check|rhgb|quiet|rd)[^[:space:]]*") > $KARGS
  echo "$ADDITIONAL_KARGS" >> $KARGS
  ln tftpboot/$KERNEL $KERNEL
  ln tftpboot/$INITRD $INITRD
  debug "Uploading files"
  add_profile "$PROFILENAME" "$KERNEL" "$INITRD" "$KARGS"
  sudo rm -rf tftpboot $KERNEL $INITRD $KARGS
}

run_testplan_on_iso() # Add an ISO as a profile an test it with the given testsuite
{
  FUNC_USAGE="$0 $FUNCNAME <TESTPLAN> <ISONAME> [<ADDITIONAL_KARGS>]"
  TESTPLAN=$1
  ISONAME=$2
  ADDITIONAL_KARGS=$3

  [[ -z $TESTPLAN ]] && die "Testplan is mandatory."
  [[ -e $ISONAME ]] || die "Isoname is mandatory."

  PROFILENAME=$(basename "$ISONAME")

  debug "Adding profile from ISO '$ISONAME'"
  add_profile_from_iso "$PROFILENAME" "$ISONAME" "$ADDITIONAL_KARGS"

  debug "Submitting testplan '$TESTPLAN'"
  testplan_submit "$TESTPLAN" "tbd_profile=$PROFILENAME"

  debug "Waiting for testplan '$TESTPLAN' to end"
  wait_testplan "$TESTPLAN"

  debug "Testplan '$TESTPLAN' ended, removing profile '$PROFILENAME'"
  remove_profile "$PROFILENAME"
}

#
# Executive part
#
if _is_command $1
then
  "${@}"
elif [[ -z $@ ]]
then
  help
  exit 1
else
  error "ERROR: Unknown function '$1'"
  help
  exit 1
fi

# vim: sw=80:
