
PYTHONBINS := bin/igord bin/igorc
PYTHONSOURCES := $(shell find igor -name \*.py -not -path */hacks.py)
PYTHONSOURCES += $(PYTHONBINS)
XMLSOURCES := $(shell find . -name \*.xml -or -name \*.xsl)

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


#
# Check related stuff
#
check-local: check-static-doctests check-static-pep8 check-static-pyflakes check-static-pylint
	@echo -e "---\n Passed $@\n---"

check-static-xmllint: $(XMLSOURCES:%=%.xmllint)
	@echo Passed $@

%.xmllint:
	xmllint --noout "$*"

check-static-doctests: $(PYTHONSOURCES:%=%.doctest)
	@echo Passed $@

%.doctest:
	PYTHONPATH=. python -m doctest "$*"

check-static-pep8: $(PYTHONSOURCES:%=%.pep8)
	@echo Passed $@

%.pep8:
	PYTHONPATH=. pep8 -r "$*"

PYLINT=pylint -f parseable --include-ids=yes --rcfile=.pylintrc
check-static-pylint: $(PYTHONSOURCES:%=%.pylint)
	@echo Passed $@

%.pylint:
	PYTHONPATH=. $(PYLINT) "$*"

check-static-pyflakes: $(PYTHONSOURCES:%=%.pyflakes)
	@echo Passed $@

%.pyflakes:
	PYTHONPATH=. pyflakes "$*"
