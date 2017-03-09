#!/usr/bin/make
PYTHON := /usr/bin/env python3
REACTIVE_DIR := $(PWD)/reactive
TEST_PREFIX := PYTHONPATH=$(REACTIVE_DIR)
TEST_DIR := $(PWD)/unit_tests
CHARM_DIR := $(PWD)

all: lint test

lint:
	@flake8 $(wildcard hooks reactive unit_tests tests)

test:
	@echo Starting tests...
	@CHARM_DIR=$(CHARM_DIR) $(TEST_PREFIX) nosetests -s $(TEST_DIR)

clean:
	rm -f $(REACTIVE_DIR)/*.pyc $(TEST_DIR)/*.pyc

build:
	@charm build -o $(JUJU_REPOSITORY)

unit_test:
	@echo Starting tests...
	tox
