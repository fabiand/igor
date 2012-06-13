

all: rpm dist
	echo Done

build:
	python setup.py build -f

rpm: build
	python setup.py bdist_rpm

dist: build
	python setup.py sdist


install: rpm
	yum -y localinstall dist/igor-*.noarch.rpm
	-systemctl daemon-reload

start:
#	-systemctl enable igord.service
	-systemctl start igord.service
	-systemctl status igord.service

stop:
	-systemctl stop igord.service

uninstall: stop
	-systemctl disable igord.service
	-yum -y remove igor

