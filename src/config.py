TESTCASES_PATH = "testcases"
COBBLER_URL = "http://127.0.0.1:25151/"

COBBLER_KARGS_INSTALL = " BOOTIF=eth0 storage_init firstboot"
COBBLER_KARGS =" local_boot_trigger=192.168.122.1:8080/testjob/${igor_cookie}"
#COBBLER_KARGS += " adminpw=%s" % run("openssl passwd -salt OMG 123123")
