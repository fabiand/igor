
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
Currently two:

1. `pre-job`: Triggered before each job
2. `post-job`: Triggered after each job

Just request a new hook if you need one.


How can I use hooks?
--------------------
You can use the hooks to connect igor with a 3rd party application.


How can I write a hook?
-----------------------
A hook is a scripts residing in a specififc path (look at ``igord.cfg``).
The file itself is an executable script (bash, python, ...).
The only data which is passed (as the first parameter) to a hook is the cookie
or job id.

Example::

  $ HOOKPATH=/etc/igord/post-job.d/         # If this is the hook path
  $ mkdir -p $HOOKPATH
  $ cd $HOOKPATH
  $ edit send-mail-to-someone.sh
  $ chmod a+x send-mail-to-someone.sh

This scripts is now run after each job.


How can I retrieve more data about the job?
-------------------------------------------
You can use the cookie together with the RESTless API of Igor to get all kinds
of data/artifacts about the job and push this into your application.

:Note:
  Take a close look at the ``/jobs/<cookie>/status`` API call, as this
  is an XML document with all relevant informations.
  You can access the e.g. 

  1. list artifacts using ``/jobs/<cookie>/artifacts/``
  2. artifacts directly using ``/jobs/<cookie>/artifacts/somelog.txt``
