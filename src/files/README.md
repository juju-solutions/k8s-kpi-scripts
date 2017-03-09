This is a set of scripts used to push data for the openstack KPI dashboard at
<https://openstack.kpi.canonical.com/dashboard/db/kpis>

## `internal`

This directory contains scripts that are wired into our own internal systems,
such as our GNU Mailman server at lists.ubuntu.com.  It is not meant to be run
arbitrarily.

## `thirdparty`

This directory contains scripts that should (in the presence of appropriate
configuration files) work from any host that has access to both the
push-gateway and remote services (such as github and stackoverflow).  It should
be possible to run-parts this directory hourly.
