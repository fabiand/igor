#!/usr/bin/python -u

import libvirt
import threading
import time

def eventToString(event):
    eventStrings = ( "Defined",
                     "Undefined",
                     "Started",
                     "Suspended",
                     "Resumed",
                     "Stopped",
                     "Shutdown" );
    return eventStrings[event];

def detailToString(event, detail):
    eventStrings = (
        ( "Added", "Updated" ),
        ( "Removed" ),
        ( "Booted", "Migrated", "Restored", "Snapshot" ),
        ( "Paused", "Migrated", "IOError", "Watchdog" ),
        ( "Unpaused", "Migrated"),
        ( "Shutdown", "Destroyed", "Crashed", "Migrated", "Saved", "Failed", "Snapshot"),
        ( "Finished" )
        )
    return eventStrings[event][detail]

def virEventLoopNativeRun():
    while True:
        libvirt.virEventRunDefaultImpl()

def virEventLoopNativeStart():
    global eventLoopThread
    libvirt.virEventRegisterDefaultImpl()
    eventLoopThread = threading.Thread(target=virEventLoopNativeRun, name="libvirtEventLoop")
    eventLoopThread.setDaemon(True)
    eventLoopThread.start()

def myDomainEventCallback2 (conn, dom, event, detail, opaque):
    print "myDomainEventCallback2 EVENT: Domain %s(%s) %s %s" % (dom.name(), dom.ID(),
                                                                 eventToString(event),
                                                                 detailToString(event, detail))

def main():
    virEventLoopNativeStart()

    vc = libvirt.openReadOnly("qemu:///system")

    vc.domainEventRegisterAny(None, libvirt.VIR_DOMAIN_EVENT_ID_LIFECYCLE, myDomainEventCallback2, None)

#    vc.setKeepAlive(5, 3)
#    while vc.isAlive() == 1:
#        time.sleep(1)

    time.sleep(30)


if __name__ == "__main__":
    main()
    print("done")

