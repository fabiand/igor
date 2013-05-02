
include Makefile.check


SHELL := /bin/bash
.PHONY: dist


all: rpm dist
	echo Done

run:
	PYTHONPATH=. python bin/igord

build:
	python setup.py build -f

rpm: build
	python setup.py bdist_rpm

dist: build
	python setup.py sdist

clean:
	rm -rvf dist build
