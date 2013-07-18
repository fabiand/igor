
Igor
====

Igor is a small tool for continous test automation linux distributions.
The tool tries not to distinguish (when it comes to testsuites) between VMs and real hardware.
Initially Igor was developed in the cosmos of [oVirt Node](http://www.ovirt.org/Node)
Igor is intended to be combined with jenkins.


Ingredients
-----------
- libvirt
- python
-- python-bottle (bottlepy)
-- libvirt-python
- (Optionally, or for real hardware) A working cobbler environment


10,000 feet view
----------------
Igor knows about hosts, profiles and testsuites.

The daemon prepares a host with a given profile.
Afterwards it is expected that a client script is run by the host to run a 
number of testcases (structured into testsuites, testsets and testcases).

Multiple tuples of (host, profile, testsuite) form a testplan.

Igor - the daemon - takes care of these items (host, profile, testsuite). Once a host is provisioned and started, it's up to the slave to initiate the testing.
The communication between the daemon and the slave happens via an RESTish API.

`igorc` is the client tool to manage the daemon. E.g. create profiles and submit jobs.

Additionally there is a UI mainly intended to monitor the status of running jobs. It can be found at <http://localhost:8080>.


Getting started using Fedora 19 and libvirt
-------------------------------------------
igor is now part of Fedora and can be installed using:

    $ sudo yum install igor igor-client

The igor-slave - which is needed on the system under test - can be installed using the `igor-slave` package:

    $ sudo yum install igor-slave


Getting started using git
-------------------------
Ensure to install some common components:

    $ sudo yum -y groupinstall virtualization fedora-packager
    $ sudo yum -y install python-bottle libvirt-python python-lxml parted \
                          lvm2 openssh-clients isomd5sum

Now run it:

    $ cp data/igord.cfg.example ~/igord.cfg     # Or: /etc/igord/igord.conf
    $ edit ~/igord.cfg
    $ mkdir /var/run/igord
    $ PYTHONPATH=. ./bin/igord

Or: Build and install igord:

    $ make install                              # Will build and install igord
    $ cp data/igord.cfg.example /etc/igord.d/igord.cfg
    $ edit /etc/igord.d/igord.cfg
    $ service igord start
    $ service igord status


Firewall
--------
The slaves (the SUT) is communicating with Igor using it's RESTish API, therefor you need to open a port:

    $ sudo iptables -I INPUT -m tcp -p tcp --dport 8080 -j ACCEPT

or with firewalld:

    $ sudo firewall-cmd --add-port 8080/tcp

The client
----------
If the daemon is running you can use `igorc` to run jobs.

Basic usage:

    $ PYTHONPATH=. bin/igorc -h


Get a list of available commands:

    $ PYTHONPATH=. bin/igorc help

And run a testplan on an oVirt Node ISO:

    # Most high-level one is testplan_on_iso:
    # Get some help on the command
    $ PYTHONPATH=. bin/igorc testplan_on_iso
    # And how to use it:
    $ PYTHONPATH=. bin/igorc -n testplan_on_iso \
        ai_extended
        ovirt-node-iso-3.0.0-5.0.1.igor-slave.fc18.iso
        'local_boot_trigger=192.168.122.1:8080/testjob/{igor_cookie}'


To be continued ➫
