#!/bin/bash

[[ -e .igord-cookie ]] && . .igord-cookie || {
    echo "Please put the igord session/cookie into .igord-cookie"
    exit 1
}

debug() { echo "$SESSION $(date) - $@" >&2 ; }

api()
{
  URL=${APIURL:-http://localhost:8080/}${1#/}
  debug "Calling $URL"
  curl --silent "$URL"
}

jobs() { api jobs ; }

# '/job/submit/<testsuite>/with/<profile>/on/<host>/<cookiereq>'
submit() { api job/$1/with/$2/on/$3 ; }

$@

# vim: set sw=2:
