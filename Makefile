
PYTHONSOURCES=$(shell find igor -name \*.py) bin/igord

all: rpm dist
	echo Done

build:
	python setup.py build -f

rpm: build
	python setup.py bdist_rpm

dist: build
	python setup.py sdist

clean:
	rm -rvf dist build

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

check-local: doctests pep8 pyflakes
	@echo -e "---\n Passed.\n---"

doctests:
	@for M in $(PYTHONSOURCES); \
	do \
		echo Doctest on "$$M"; \
		PYTHONPATH=. python -m doctest $$M || exit 1; \
	done

pep8:
	@for M in $(PYTHONSOURCES); \
	do \
		echo pep8 on "$$M"; \
		PYTHONPATH=. pep8 -r $$M || exit 1; \
	done

pylint:
	@for M in $(PYTHONSOURCES); \
	do \
		echo pylint on "$$M"; \
		PYTHONPATH=. pylint $$M || exit 1; \
	done

pyflakes:
	@for M in $(PYTHONSOURCES); \
	do \
		echo pyflakes on "$$M"; \
		PYTHONPATH=. pyflakes $$M || exit 1; \
	done
