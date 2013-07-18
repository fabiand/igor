
====
Igor
====

Igor is a small daemon to continous automated testing of pxe based linux
distributions with cobbler, libvirt and real hardware.
Intended to be combined with jenkins.


Ingredients
===========
- Working cobbler environment
- libvirt
- python
-- python-bottle (bottlepy)
-- libvirt-python


Overview
========
Basically a daemon prepares hosts and tells cobbler what profile to assign to 
them.
Afterwards it is expected that a client script is run by the host to run a 
number of testcases (structured into testsuites, testsets and testcases).


Pitfalls & Requirements
=======================
- It is currently expected that the images are on the host where VMs are 
  spawned.
- A working cobbler environment is expected
- shh-copy-id the keys to the cobbler server when Cobbler.Jenkins_Injection is
  used, as the ISO is scp'ed onto the cobbler server


Getting started
using Fedora 16 and libvirt
===========================
Ensure to install some common components::

    $ sudo yum -y groupinstall virtualization fedora-packager
    $ sudo yum -y install python-bottle libvirt-python python-lxml parted \
                          lvm2 openssh-clients isomd5sum

Now run it::

    $ cp data/igord.cfg.example ~/igord.cfg     # Or: /etc/igord/igord.conf
    $ edit ~/igord.cfg
    $ mkdir /var/run/igord
    $ PYTHONPATH=. ./bin/igord

Or: Build and install igord::

    $ make install                              # Will build and install igord
    $ cp data/igord.cfg.example /etc/igord.d/igord.cfg
    $ edit /etc/igord.d/igord.cfg
    $ service igord start
    $ service igord status


Firewall and Cobbler API
------------------------
Considder opening the appropriate firewall port, e.g.:
$ sudo iptables -I INPUT -m tcp -p tcp --dport 8080 -j ACCEPT

Also note that Cobbler's API is just allowing local connections, you might
want to tunnel the daemons calls:
$ ssh $COBBLERSERVER -L25151:127.0.0.1:25151


The client
----------
If the daemon is running you can use `igorc` to run jobs::

    $ PYTHONPATH=. bin/igorc -h

    # Get a list of available commands:
    $ PYTHONPATH=. bin/igorc help

    # Most high-level one is testplan_on_iso:
    # Get some help on the command
    $ PYTHONPATH=. bin/igorc testplan_on_iso
    # And how to use it:
    $ PYTHONPATH=. bin/igorc -n testplan_on_iso \
        ai_extended
        ovirt-node-iso-3.0.0-5.0.1.igor-slave.fc18.iso
        'local_boot_trigger=192.168.122.1:8080/testjob/{igor_cookie}'


                                ~ To be continued ~
