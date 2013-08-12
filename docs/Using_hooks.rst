
================
How to use hooks
================

:Authors:
    Fabian Deutsch <fabiand@fedoraproject.org>

What are hooks?
---------------
Hooks are called on specific events (see below), they then call hook-handlers
which are scripts in a predefined directory on the filesystem.

The hook-handler scripts is called with two arguments:
1. The hookname
2. The session id


What events trigger hooks?
--------------------------
Currently:

* post-annotate
* post-end
* post-job
* post-setup
* post-start
* post-testcase
* pre-job

Just request a new hook if you need one.


How can I use hooks?
--------------------
You can use the hooks to connect igor with a 3rd party application.


How can I write a hook?
-----------------------
A hook is a scripts residing in a specific path (look at ``igord.cfg``).
The file itself is an executable script (bash, python, ...).

Two params are passed to each hook:
 1. The hook name
 2. The cookie (or session id)

Example for a hook-handler::

  $ HOOKPATH=/etc/igord/hook.d/         # If this is the hook path
  $ mkdir -p $HOOKPATH
  $ cd $HOOKPATH
  $ cat > push-to-redis.sh <<EOF
  HOOKNAME=$1
  SESSION=$2

  # Only react on post-job events
  if [[ "$HOOKNAME" == "post-job" ]]
  then
    redis publish com.example.events "$HOOKNAME:$SESSION"
  fi
  EOF
  $ chmod a+x push-to-redis.sh

This scripts is now run on each event - because the script reacts to all
events.


How can I retrieve more data about the job?
-------------------------------------------
You can use the cookie together with the RESTless API of Igor to get all kinds
of data/artifacts about the job and push this into your application.

You can also use `` igorc`` to gather more informations.

:Note:
  Take a close look at the ``/jobs/<cookie>/status`` API call, as this
  is an XML document with all relevant informations.
  You can access the e.g. 

  1. list artifacts using ``/jobs/<cookie>/artifacts/``
  2. getting an artifact: ``/jobs/<cookie>/artifacts/0-annotations.yaml``
