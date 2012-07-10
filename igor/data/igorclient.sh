#!/bin/bash

IGORCOOKIEFILE=~/.igorcookie
DEBUG=${DEBUG:-true}

#
# Common functions
#
debug() { [[ -z $DEBUG ]] || echo "${IGORCOOKIE:-(no session)} $(date) - $@" >&2 ; }
error() { echo -e "\n$@\n" >&2 ; }
die() { error $@ ; exit 1 ; }

help() # This help
{
  echo -e "usage: $0 FUNCTION\n\nFUNCTION:"
  grep "[[:alnum:]]() #" $0 | sort | sed "s/#/\t/ ; s/()//"
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

#
# API stateless functions
#
jobs() # List all jobs
{
  api jobs
}

submit() # Submit a new job, e.g. submit <testsuite> <profile> <host>
{
  TMPFILE=$(mktemp)
  api submit/$1/with/$2/on/$3 | tee $TMPFILE
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
  api job/abort/$IGORCOOKIE
  uncookie
}


start() # Start the current job
{
  has_cookie
  api job/start/$IGORCOOKIE
}

status() # Get the status of the current job
{
  has_cookie
  api job/status/$IGORCOOKIE
}

report() # Get the rst report
{
  has_cookie
  api job/report/$IGORCOOKIE
}

testsuite() # Get the testsuite for the current job
{
  ARCHIVE=${1:-testsuite.tar.bz2}
  has_cookie
  api /job/testsuite/for/$IGORCOOKIE > $ARCHIVE
}

artifacts() # Get all artifacts for the current job
{
  ARCHIVE=${1:-artifacts.tar.bz2}
  has_cookie
  api job/artifact/from/$IGORCOOKIE > $ARCHIVE
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

  ARCHIVE="/tmp/$PNAME_files.tar"
  tar -c -f $ARCHIVE $KERNEL $INITRD $KARGS

  URL=$(_api_url profiles/$PNAME)
  curl --header "x-kernel-filename: $KERNEL" \
       --header "x-initrd-filename: $INITRD" \
       --header "x-kargs-filename: $KARGS" \
       --upload-file $ARCHIVE "$URL"

  rm -f $ARCHIVE
# Slow:  curl -F "kernel=@$KERNEL" -F"initrd=@$INITRD" -F"kargs=@$KARGS" "$URL"
}
remove_profile() # Remove a profile
{
  PNAME=$1
  [[ -z $PNAME ]] && die "Profile name is mandatory."
  api /profiles/$PNAME/remove
}
profile_kargs() # Set the kernel arguments of a profile
{
  PNAME=$1
  KARGS=$2
  [[ -z $PNAME ]] && die "Profile name is mandatory."
  [[ -z $KARGS ]] && die "kargs are mandatory."
  URL=$(_api_url profiles/$PNAME)
  curl --data "kargs=$KARGS" "$URL"
}

testplan_submit() # Submit a testplan to be run
{
  PNAME=$1
  [[ -z $PNAME ]] && die "Testplan name is mandatory."
  api /testplans/$PNAME/submit
}

testplan_abort() # Abort a running testplan to be run
{
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
  api job/status/$IGORCOOKIE | _filter_key state
}

wait_state() # Wait until a specific state is reached (regex)
{
  EXPR=$1
  INTERVAL=${2:-10}
  STATE=""
  has_cookie
  echo -n "Waiting "
  export DEBUG=""
  TIME_START=$(date +%s)
  TIMEOUT=$(api job/status/$IGORCOOKIE | grep timeout | tail -n1 | _filter_key timeout)
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
  exit 0
}

abort_all() # Abort all jobs
{
  jobs | _filter_key id | while read IGORCOOKIE
  do
    debug "Aborting $IGORCOOKIE"
    abort
  done
}

#
# Executive part
#
if _is_command $1
then
  ${@}
else
  error "ERROR: Unknown function '$1'"
  help
  exit 1
fi

# vim: sw=2 tw=2:
