#!/bin/bash

IGORCOOKIEFILE=~/.igorcookie

#
# Common functions
#
debug() { echo "${IGORCOOKIE:-(no session)} $(date) - $@" >&2 ; }
error() { echo -e "\n$@\n" >&2 ; }

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

api()
{
  URL=${APIURL:-http://localhost:8080/}${1#/}
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
    cat $IGORCOOKIEFILE
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
  api job/abort/$IGORCOOKIE/True
  uncookie
}

end() # End the current job and remove it's artifacts
{
  has_cookie
  api job/end/$IGORCOOKIE
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

#
# Convenience functions
#
state() # Just get the value of the status key
{
  has_cookie
  api job/status/$IGORCOOKIE | _filter_key state
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
if _is_command $@
then
  ${@}
else
  error "ERROR: Unknown function '$1'"
  help
  exit 1
fi

# vim: sw=2 tw=2:
