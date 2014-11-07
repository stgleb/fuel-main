#    Copyright 2013 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from proboscis import SkipTest
from proboscis import test

from fuelweb_test.helpers.decorators import log_snapshot_on_error
from fuelweb_test.settings import DEPLOYMENT_MODE, NEUTRON_ENABLE
from fuelweb_test.settings import OPENSTACK_RELEASE
from fuelweb_test.settings import OPENSTACK_RELEASE_REDHAT
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic
from fuelweb_test import logger, settings

from fuelweb_test.tests.base_test_case import revert_snapshot
from fuelweb_test.tests.base_test_case import bootstrap_nodes
from fuelweb_test.tests.base_test_case import cluster_template
from certification_script import cert_script

@test(groups=["pullrequest"])
class TestPullRequest(TestBasic):
    @test(depends_on=[SetupEnvironment.prepare_release],
          groups=["pullrequest"])
    @log_snapshot_on_error
    @revert_snapshot("ready_with_3_slaves")
    @cluster_template("pullrequest1")
    def deploy_pr_ha(self,cluster_templ):
        """Deploy cluster in HA mode with Neutron GRE

        Scenario:
            1. Create cluster with gre
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Deploy the cluster
            5. Validate cluster network

        Snapshot: deploy_pr_ha

        """

        if OPENSTACK_RELEASE == OPENSTACK_RELEASE_REDHAT:
            raise SkipTest()

        if not cluster_templ.get('release'):
            cluster_templ['release'] = 1

        with cert_script.make_cluster(self.conn, cluster_templ) as cluster:


            self.fuel_web.run_ostf(cluster_id=cluster.id)