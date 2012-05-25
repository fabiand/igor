#!/bin/bash

debug() { echo "${SESSION:-(no session)} $(date) - $@" >&2 ; }

api()
{
  URL=${APIURL:-http://localhost:8080/}${1#/}
  debug "Calling $URL"
  curl --silent "$URL"
  echo ""
}

has_cookie() 
{
  [[ -e $IGORCOOKIE ]] || {
      echo "Please put the igord session/cookie into .igord-cookie"
      exit 1
  }
}

jobs() # List all jobs
{
  api jobs
}

# '/job/submit/<testsuite>/with/<profile>/on/<host>/<cookiereq>'
submit() # Submit a new job, e.g. submit <testsuite> <profile> <host>
{
  api submit/$1/with/$2/on/$3
}

abort() # Abort the current job
{
  has_cookie
  api job/abort/$IGORCOOKIE/True
}

help() # This help
{
  echo -e "usage: $0 FUNCTION\nFUNCTION:"
  grep "[[:alnum:]]() #" $0 | sort | sed "s/#/\t/ ; s/()//"
}

${@:-help}

# vim: set sw=2:
