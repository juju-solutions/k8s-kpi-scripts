#!/usr/bin/env python3

"""
Copyright (c) 2016 Canonical, Ltd.
Authors: Paul Gear, James Page, konstantinos Tsakalozos

Hooks for k8s-kpi-scripts charm.
"""

import glob
import os
import re

from charmhelpers.core import (
    host,
    hookenv,
    unitdata,
)

from charms.reactive import (
    remove_state,
    set_state,
)

from charms.reactive.decorators import (
    hook,
    when,
    when_all,
    when_not,
)

from charmhelpers.fetch import apt_install

from charmhelpers.core.templating import render


CHARM_NAME = 'k8s-kpi-scripts'


def status(status, msg):
    hookenv.log('%s: %s' % (status, msg))
    hookenv.status_set(status, msg)


def active(msg):
    status('active', msg)


def blocked(msg):
    status('blocked', msg)


def maint(msg):
    status('maintenance', msg)


def write_config_file():
    """
    Create /etc/k8s-kpi-scripts.ini.
    """
    cfg_file = '{}.ini'.format(CHARM_NAME)
    kv = unitdata.kv()
    push_gateway = kv.get('push_gateway')
    maint('rendering config %s' % (cfg_file,))
    script_dir = '/srv/{}/parts'.format(CHARM_NAME)
    scripts = [x for x in os.listdir(
        script_dir) if re.match(r'^[-_A-Za-z0-9]+$', x)]
    render(
        source=cfg_file,
        target='/etc/' + cfg_file,
        perms=0o755,
        context={
            'push_gateway': push_gateway,
            'scripts': scripts,
            'config': hookenv.config(''),
        },
    )
    return push_gateway


def write_cron_job():
    """
    Create cron job
    """
    dst = '/etc/cron.d/{}'.format(CHARM_NAME)
    cron_job = 'cron-job'
    maint('installing %s to %s' % (cron_job, dst))
    kv = unitdata.kv()
    render(
        source=cron_job,
        target=dst,
        perms=0o755,
        context={
            'script_dir': '/srv/{}/parts'.format(CHARM_NAME),
            'script_name': CHARM_NAME,
            'user': kv.get('run-as'),
        },
    )


@when_all(
    '{}.configured'.format(CHARM_NAME),
    'push_gateway.configured',
)
def write_config():
    blocked('Unable to configure charm - please see log')
    push_gateway = write_config_file()
    write_cron_job()
    active('Configured push gateway %s' % (push_gateway,))


@when('juju-info.available')
def relation_joined(relation):
    """
    Get private address of push gateway from juju-info relation;
    save in unit data.
    cf. https://gist.github.com/marcoceppi/fb911c63eac6a1db5c649a2f96439074
    """
    remove_state('push_gateway.configured')
    push_gateway = relation.private_address()
    kv = unitdata.kv()
    kv.set('push_gateway', push_gateway)
    kv.flush()
    set_state('push_gateway.configured')
    active('Set push_gateway.configured state')


@when_not('push_gateway.configured')
def not_configured():
    blocked('Waiting for push-gateway relation')


@hook('config-changed')
def config_changed():
    remove_state('{}.configured'.format(CHARM_NAME))
    maint('checking configuration')

    kv = unitdata.kv()
    config_items = (
        'run-as',
    )
    for c in config_items:
        item = hookenv.config(c)
        if not item:
            blocked('%s must be set' % (c,))
            remove_state('{}.configured'.format(CHARM_NAME))
            return
        else:
            kv.set(c, item)
    set_state('{}.configured'.format(CHARM_NAME))


@hook(
    'install',
    'upgrade-charm',
)
def install_files():
    # this part lifted from haproxy charm hooks.py
    src = os.path.join(os.environ["CHARM_DIR"], "files/thirdparty/")
    dst = '/srv/{}/parts/'.format(CHARM_NAME)
    maint('Copying scripts from %s to %s' % (src, dst))
    host.mkdir(dst, perms=0o755)
    for fname in glob.glob(os.path.join(src, "*")):
        host.rsync(fname, os.path.join(dst, os.path.basename(fname)))

    # Template files may have changed in an upgrade, so we need to rewrite
    # them
    config_changed()

    # Package prerequisites for k8s-kpi-scripts/thirdparty/*
    apt_install([
        'python-configparser',
        'python-prometheus-client',
        'python-cssselect',
        'python-yaml',
        'python-urllib3',
    ])
