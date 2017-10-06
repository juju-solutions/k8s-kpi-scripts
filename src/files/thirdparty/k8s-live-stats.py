#!/usr/bin/env python2


from collections import defaultdict
import glob
import gzip
import re
import os
import logging

from datetime import datetime
from kpi_common import get_push_gateway
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway


logs = [
    glob.glob('/var/tmp/logs/api/1/api.jujucharms.com.log-201*'),
    glob.glob('/var/tmp/logs/api/2/api.jujucharms.com.log-201*'),
]

clouds = ['maas', 'ec2', 'azure', 'gce', 'lxd', 'openstack', 'manual', 'vsphere']

app_id = 'cs%3A~containers%2Fkubernetes-master'


uuid_re = 'environment_uuid=[\w]{8}-[\w]{4}-[\w]{4}-[\w]{4}-[\w]{12}'
cloud_re = 'provider=[^,\"]*'
region_re = 'cloud_region=[^,\"]*'
version_re = 'controller_version=[^,\"]*'
app_re = '[&?]id=[^&,\"]*'
apps = defaultdict(list)
running = {}


def find_uuid(l):
    """
    Find the uuid of a request in a log line
    Args:
        l: the line

    Returns: the UUID or None

    """
    m = re.search(uuid_re, l)
    if m:
        uuid = m.group(0)
        return uuid.split('=')[1]
    else:
        return None


def find_metadata(l, date):
    """
    Return metadata of the request given it refers to the app id provided
    Args:
        l: the log line
        date: the date of the log

    Returns: a dictionary with request metadata

    """
    app = re.search(app_re, l)

    found = None
    if app:
        c = re.search(cloud_re, l)
        cr = re.search(region_re, l)
        v = re.search(version_re, l)
        cloud = 'pre-2'
        region = 'pre-2'
        version = 'pre-2'

        if c:
            _, cloud = c.group().split('=')

        if cr:
            _, region = cr.group().split('=')

        if v:
            _, version = v.group().split('=')

        _, found = app.group().split('=')

        return {
            "app": found,
            "cloud": cloud,
            "region": region,
            "version": version,
            "start": date,
            "end": date,
        }

    return found


def register_online_deployments(registry, data):
    for cloud in clouds:
        online_in_cloud = Gauge(
            'live_ks_deployments_online_on_{}_cloud'.format(cloud),
            'Online deployments in {}'.format(cloud),
            ['cloud'],
            registry=registry,
        )
        online_cloud_deps_num = len(list(filter(lambda deployment:
                                          deployment['online'] == True and
                                          deployment['cloud'] == cloud, data)))
        online_in_cloud.labels(cloud).set(online_cloud_deps_num)


def register_age_deployments(registry, data):
    online_age = Gauge(
        'live_ks_age_online_deployments',
        'Age of online deployments',
        ['online'],
        registry=registry,
    )
    for age in range(1,180):
        online_age_deps_num = len(list(filter(lambda deployment:
                                          deployment['online'] == True and
                                          deployment['days'] == age, data)))
        online_age.labels(age).set(online_age_deps_num)


def register_period(registry, data, label):
    all_deployments_gauge = Gauge(
        'live_ks_deployments_{}'.format(label),
        'Deployment in all clouds',
        registry=registry,
    )
    all_deployments_gauge.set(len(data))

    all_long_deployments_gauge = Gauge(
        'live_ks_deployments_longlasting_{}'.format(label),
        'Deployment in all clouds with lifespan greater than 2 weeks',
        registry=registry,
    )
    long_deps_num = len(list(filter(lambda deployment: deployment['days'] > 14, data)))
    all_long_deployments_gauge.set(long_deps_num)

    for cloud in clouds:
        deployments_in_cloud = Gauge(
            'live_ks_deployments_{}_{}'.format(cloud, label),
            'Deployments in {} for {}'.format(cloud, label),
            registry=registry,
        )
        cloud_deps_num = len(list(filter(lambda deployment:
                                          deployment['cloud'] == cloud, data)))
        deployments_in_cloud.set(cloud_deps_num)

        long_deployments_in_cloud = Gauge(
            'live_ks_deployments_longlasting_{}_{}'.format(cloud, label),
            'Deployments in {} for {} with lifespan greater than 2 weeks'.format(cloud, label),
            registry=registry,
        )
        long_cloud_deps_num = len(list(filter(lambda deployment: deployment['days'] > 14 and
                                         deployment['cloud'] == cloud, data)))
        long_deployments_in_cloud.set(long_cloud_deps_num)


def main():

    lastlogdate = datetime.strptime("20000101", '%Y%m%d')
    for g in logs:
        print("Found logs {0}".format(len(g)))
        for path in g:
            print("Processing: {0}".format(path))
            logname = os.path.basename(path)
            datestr = logname.\
                replace('api.jujucharms.com.log-', '').\
                replace('.anon', '').\
                replace('.gz', '')
            print("Date {}".format(datestr))
            processingdate = datetime.strptime(datestr, '%Y%m%d')
            if processingdate > lastlogdate:
                lastlogdate = processingdate
            try:
                with gzip.open(path) as f:
                    lines = f.read().split("\n")
            except IOError:
                print("Corrupted. Skipping date {}".format(datestr))

            for l in lines:
                uuid = find_uuid(l)
                if uuid:
                    data = find_metadata(l, datestr)
                    if not data or app_id not in data['app']:
                        continue

                    if uuid not in apps:
                        apps[uuid] = data
                    else:
                        data = apps[uuid]
                        if data['start'] > datestr:
                            data['start'] = datestr
                        if data['end'] < datestr:
                            data['end'] = datestr

    print("Found UUIDs")
    print(len(apps.keys()))

    pkg = 'k8s-kpi-scripts'
    name = 'k8s-live-stats'
    gateway = get_push_gateway(pkg, name)
    registry = CollectorRegistry()
    logging.basicConfig(level=logging.DEBUG)

    month_dataset = []
    three_month_dataset = []
    six_month_dataset = []
    for uuid, data in apps.items():
        start = datetime.strptime(data['start'], '%Y%m%d')
        end = datetime.strptime(data['end'], '%Y%m%d')
        days = (end - start).days + 1
        if (lastlogdate - end).days > 0:
            data['online'] = False
        else:
            data['online'] = True
        data['days'] = days

        today = datetime.now()
        if (today - start).days <= 180:
            six_month_dataset.append(data)
        if (today - start).days <= 90:
            three_month_dataset.append(data)
        if (today - start).days <= 30:
            month_dataset.append(data)
        print("{} {}".format(uuid, data))

    register_age_deployments(registry, list(apps.values()))
    register_online_deployments(registry, list(apps.values()))
    register_period(registry, six_month_dataset, "six_months")
    register_period(registry, three_month_dataset, "three_months")
    register_period(registry, month_dataset, "one_month")

    push_to_gateway(gateway, job=name, registry=registry)

if __name__ == "__main__":
    main()
