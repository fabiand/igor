
# Path of testcases relative to runpath
TESTCASES_PATH = "../testcases"

# The URL of Cobblers API
COBBLER_URL = "http://127.0.0.1:25151/"

# Kernel arguments to be used for installation/pxe and default boot
COBBLER_KARGS_INSTALL = " BOOTIF=eth0 storage_init firstboot"
COBBLER_KARGS =" local_boot_trigger=192.168.122.1:8080/testjob/${igor_cookie}"
#COBBLER_KARGS += " adminpw=%s" % run("openssl passwd -salt OMG 123123")
