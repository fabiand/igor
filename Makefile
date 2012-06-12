

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
	-systemctl enable igord.service
	-systemctl start igord.service
	-systemctl status igord.service

uninstall:
	-systemctl stop igord.service
	-systemctl disable igord.service
	-yum -y remove igor

