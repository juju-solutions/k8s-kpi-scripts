
import os
import configparser
import logging

from launchpadlib.launchpad import Launchpad
from launchpadlib.uris import lookup_service_root
from launchpadlib import credentials

from prometheus_client import Gauge


BUG_IMPORTANCE = [
   'Unknown',
   'Undecided',
   'Critical',
   'High',
   'Medium',
   'Low',
   'Wishlist',
]

BUG_STATUS = [
    'New',
    'Incomplete',
    'Triaged',
    'In Progress',
    'Confirmed',
]


def get_push_gateway(pkg, name):
    """Find push gateway in config file."""
    return get_config(pkg, name)['push-gateway']


def get_config(pkg, name):
    """
    Get configuration options for this script
    """
    config = configparser.SafeConfigParser()
    conffiles = [
        '/etc/{}.ini'.format(pkg),
        os.path.expanduser('~/.{}.ini'.format(pkg)),
        '{}.ini'.format(pkg),
    ]
    config.read(conffiles)
    return config[name]


class ShutUpAndTakeMyTokenAuthorizationEngine(credentials.RequestTokenAuthorizationEngine):

    """This stub class prevents launchpadlib from nulling out consumer_name
    in its demented campaign to force the use of desktop integration. """

    def __init__(self, service_root, application_name=None, consumer_name=None,
                 credential_save_failed=None, allow_access_levels=None):
        super(ShutUpAndTakeMyTokenAuthorizationEngine, self).__init__(
              service_root, application_name, consumer_name,
              credential_save_failed)


def launchpad_login(pkg):
    """Log into Launchpad API with stored credentials."""
    creds_dir = os.path.expanduser(os.path.join('~', '.' + pkg))
    if not os.path.exists(creds_dir):
        os.makedirs(creds_dir, 0o700)
    os.chmod(creds_dir, 0o700)
    api_endpoint = lookup_service_root('production')
    return Launchpad.login_with(
        application_name=pkg,
        credentials_file=os.path.join(creds_dir, 'launchpad.credentials'),
        service_root=api_endpoint,
        version='devel',
    )


def count_distro_bugs(distro, package):
    """Return the number of bugs for a given package."""
    source = distro.getSourcePackage(name=package)
    bugs = source.searchTasks()
    return len(bugs)


def gather_tagged_bugs(registry, projects, tags,
                       label, description):
    """Gather bugs tagged with any of tags for a list of projects."""
    gauge = Gauge(label, description,
                  ['project', 'bug_tag'],
                  registry=registry)
    for project in projects:
        for tag in tags:
            logging.info('Searching for bugs tagged'
                         ' with {} for {}'.format(tag, project))
            bugs = project.searchTasks(tags=[tag],
                                       status=BUG_STATUS)
            gauge.labels(project.name, tag).set(len(bugs))


def gather_project_bugs(registry, projects,
                        label, description):
    """Gather bugs by importance for a list of projects."""
    gauge = Gauge(label, description,
                  ['project', 'importance'],
                  registry=registry)
    for project in projects:
        logging.info('Searching for bugs for {}'.format(project))
        for importance in BUG_IMPORTANCE:
            gauge.labels(
                project.name,
                importance).set(len(
                    project.searchTasks(importance=importance,
                                        status=BUG_STATUS
                )))


def gather_bug_reporters(registry, projects, members,
                         label, description):
    """Gather bugs by reporter type for a list of projects."""
    gauge = Gauge(label, description,
                  ['project', 'reporter_type'],
                  registry=registry)
    for project in projects:
        bugs = project.searchTasks()
        canonical_bugs = []
        for member in members:
            if member.account_status != 'Active':
                continue
            bugs = project.searchTasks(bug_reporter=member)
            canonical_bugs.extend(bugs)

        bug_count = len(bugs)
        canonical_count = len(canonical_bugs)
        non_canonical_count = bug_count - canonical_count

        gauge.labels(project.name, 'internal').set(canonical_count)
        gauge.labels(project.name, 'external').set(non_canonical_count)
