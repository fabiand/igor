
==================
How to write tests
==================

:Authors:
    Fabian Deutsch <fabiand@fedoraproject.org>


Hierarchy
---------
**Testcases**
  are the atoms of igor. Testcases are scripts. In a language supported on the
  host running the script. A testcase can fail or succeed, see `Protocol - How
  testcases have to behave`_.
  Testcases are normally written in bash or python.

**Testset**
  is grouping a number of testcases. The testcases are executed in the order in
  which they appear in the testset (so it's actually more a list than a set).
  In a testse testcases can appear more  than once (even more like a list and
  not a set).
  It can defined within a testset if a *testcase* es expected to succeed
  (default) or if it is expected to fail. If the testcase behaves as expected
  then the testcase has **passed**.
  Testsets can be used to group reusable on each other depending testcases.
  For example can the testcases ``initiate_reboot`` and ``reboot_completed`` be
  grouped in the ``perform_reboot`` set.
  Additional **libraries** can also be specified in testsets.
  Testsets (a list if testcaes) are typically specified in files suffixed with
  ``.set``.

**Testsuite**
  are grouping *testsets* and are the unit which is run on the host beeing
  tested.
  If a single testcase in a suite fails, the whole suite will fail.

**Testplan**
  A testplan (currently not available, TBD) is specifying what testsuite is run
  on what host with what profile.

::

  Testplan
  |
  + Testsuite
  | |
  | + Testset
  | | |
  | | + Testcase
  | | + Testcase
  | | + Testcase
  : : :


Protocol - How **testcases** have to behave
-------------------------------------------

When a testcase behaves as expected it has **pass** the test.
There are two cases in which a testcase can pass:

1. It **succeeds** (returncode == 0) and and this is expected.
2. It **fails** (returncode != 0) and this is expected.

The first case is obvious: A testcase has passed if it succeeds.
But sometimes it is also needed to test a failure, this possible in the second
case.


Protocol - How to define a **testset**
--------------------------------------
A testset is a file with the path to a testcase in each line - relative to the
testset file.
Comments are lines starting with a hash (#).
Blank lines are ignored.

Additionall libraries can be added with lines starting with ``lib:``, e.g.:
``lib:libs/common`` would add the folder ``common`` into the testsuite
(omitting the dirname). This can be useful to add 3rd party libraries.


Protocol - How to define a **testsuite**
----------------------------------------
A *testsuite* definition file is similar to a *testset* definition file.
A *testsuite* definition file contains one *testset* file (relative to the
testsuite file) per line.
Comments are lines starting with a hash(#) and blank lines are ignored.

Libraries are not allowed in *testsuites*.


1. Preparing a filesystem structure
-----------------------------------
There is no required structure, but it's good to have a layout to not clutter
one directory with files.

  $ mkdir tcs        # For testcases
  $ mkdir libs       # For libraries

*Testsets* and *testsuites* go into the top-level directory (as there are
normally not to many of both). But you are free to also push them into
subdirectories.

:Note:
    Just be aware to keep the paths within the files in sync.


2. Creating a first testcase
----------------------------
As said earlier: testcases are simple scripts. Let's create a testcase to test
the network connectivity::

  $ cat > tcs/has_network_link.sh <<EOS
  #!/bin/bash -x

  # This testcase tests if the network has a carrier link.

  DEVICE=eth0
  ip link show $DEVICE
  ip link set dev $DEVICE up
  ip link show $DEVICE | grep "state UP"
  RETVAL=$?

  exit $RETVAL
  EOF
  $


2.a Advanced: Adding runtime dependencies to a testcase
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sometimes you want a testcase only to run if some other testcase passed.
For example: Testsing layer-3 network connectivity should only be done in
the case that a layer-2 connection was established.

That's were testcase dependencies come into play::

   $ cat > tcs/has_network_link.sh.deps <<EOF
   configure_network_link.sh
   EOF


This .deps file tells igor to only run the `has_network_link.sh` testcase
when the `configure_network_link.sh` testcase passed.


3. Creating a testset and testsuite
-----------------------------------
The testcase itself can not be run easily, it has to be part of a larger
*testset* and hat in turn part of a *testsuite*, so let's specifiy this::

  $ echo has_network_link.sh > network_eth.set
  $ echo network_eth.set > network.suite
  $


4. Adding a library - for common operations
-------------------------------------------
Some operations are quite common, like debugging or some grepping routine.
Igor itself even provides - in an extra repository - a library with common
functions.

A library is expected to reside in it's own path::

  $ mkdir -p libs/common
  $ cat > libs/common/common.sh <<EOS
  #!/bin/bash

  # A simple debugging function
  debug()
  {
    echo "$(date) - $0 - $@" >&2
  }
  EOS
  $

After creating the library itself we need to add the library to a testset,
otherwise igor won't pick it up::

  $ cat network_eth.set
  # A testset for ethernet related stuff
  lib:libs/common

  has_network_link.sh
  $
