
================
How to use hooks
================

:Authors:
    Fabian Deutsch <fabiand@fedoraproject.org>

What are hooks?
---------------
Hooks are scripts which are run at specific events (see below)


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

Example::

  $ HOOKPATH=/etc/igord/hook.d/         # If this is the hook path
  $ mkdir -p $HOOKPATH
  $ cd $HOOKPATH
  $ cat > push-to-redis.sh <<EOF
  HOOKNAME=$1
  SESSION=$2
  redis publish com.example.events "$HOOKNAME:$SESSION"
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
