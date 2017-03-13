# canonical-is-charms openstack-kpi-scripts

This provides a basic subordinate charm which installs the scripts from
files/thirdparty/ on the local system and runs them from cron.

This should be compiled with `charm build` from lp:~canonical-losas/canonical-is-charms/snappy-kpi-scripts-layer.

This charm requires a tarball (tar.gz) containing a .nova file with the
connection configuration to nova storage.

# References

- https://code.launchpad.net/~canonical-losas/canonical-is-charms/snappy-kpi-scripts/
- https://code.launchpad.net/~canonical-losas/canonical-is-charms/snappy-kpi-scripts-layer/
- https://bazaar.launchpad.net/~canonical-is/canonical-mojo-specs/trunk/files/head:/is/mojo-is-prometheus/
