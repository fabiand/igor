
================================
       Introducing Igor
================================


High-level View
---------------

A ''host'' is prepared according to a ''profile'', afterwards a numer of ''testcases'' (structured into testcases, testsets and testsuites) are run on this host.

Phase: Host Preparation
-----------------------
The host is beeing prepared to receive the profile.
For virtual hosts this is obvious: The images get allcoated, the guests are setup in e.g. libvirt.
But this can also mean to erase a hard disk of a real server using some 3rd party software.


Phase: Profile assignment
-------------------------
A profile is assigned to a host, this is mainly related to preparing cobbler or foreman or something similar to pass the given vmlinuz+initrd to a host with the given mac.


Phase: Testing
--------------
All testcases (testsets and testsuites are flattened to form a single list of testcases) are run on the host. This can also include reboots.


Phase: Cleanup
--------------
Durign the cleanup phase, which is started with some delay after the testing was completed, the host is brought down.
For VMs this can mean that images are removed and domains undefined.
