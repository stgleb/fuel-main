#    Copyright 2014 Mirantis, Inc.
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

import traceback

from proboscis import asserts
from proboscis import test
from certification_script import cert_script

from fuelweb_test.helpers.decorators import log_snapshot_on_error
from fuelweb_test import settings as hlp_data
from fuelweb_test import logger, settings
from fuelweb_test.tests import base_test_case
from fuelweb_test.tests.base_test_case import revert_snapshot
from fuelweb_test.tests.base_test_case import bootstrap_nodes
from fuelweb_test.tests.base_test_case import cluster_template
from certification_script import cert_script
from fuelweb_test.settings import DEPLOYMENT_MODE_SIMPLE



@test(groups=["thread_2", "cluster_actions"])
class EnvironmentAction(base_test_case.TestBasic):

    @test(depends_on=[base_test_case.SetupEnvironment.prepare_slaves_3],
          groups=["smoke", "deploy_flat_stop_reset_on_deploying"])
    @log_snapshot_on_error
    @cluster_template("flat")
    def deploy_flat_stop_on_deploying(self, cluster_templ):
        """Stop reset cluster in simple mode with flat nova-network

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Run provisioning task
            5. Run deployment task
            6. Stop deployment
            7. Add 1 node with cinder role
            8. Re-deploy cluster
            9. Run OSTF

        Snapshot: deploy_flat_stop_reset_on_deploying

        """
        if settings.CREATE_ENV:
            self.env.revert_snapshot("ready_with_3_slaves")

	    if not cluster_templ.get('release'):
             cluster_templ['release'] = 1

        access = {
            'tenant': 'stop_deploy',
            'user': 'stop_deploy',
            'password': 'stop_deploy'

        }
        cluster_templ['settings'].update(access)
        cluster_templ['deployment_mode'] = 'multinode'

        with cert_script.make_cluster(self.conn, cluster_templ) as cluster:
            self.fuel_web.stop_deployment_wait(cluster.id)
            cluster_id=cluster.id
            nodes = cluster.nodes
            self.fuel_web.wait_nodes_get_online_state(nodes,
                                                      nailgun_nodes=True)

            self.fuel_web.update_nodes(
                cluster_id,
                {
                    'slave-03': ['cinder']
                }
            )

            self.fuel_web.deploy_cluster_wait(cluster_id)

            asserts.assert_equal(
                3, len(self.fuel_web.client.list_cluster_nodes(cluster_id)))

            self.fuel_web.run_ostf(
                cluster_id=cluster_id)
        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_flat_stop_reset_on_deploying")

    @test(depends_on=[base_test_case.SetupEnvironment.prepare_slaves_3],
          groups=["smoke", "deploy_flat_stop_reset_on_provisioning"])
    @log_snapshot_on_error
    @cluster_template("flat")
    def deploy_flat_stop_reset_on_provisioning(self, cluster_templ):
        """Stop reset cluster in simple mode with flat nova-network

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Run provisioning task
            5. Stop deployment
            6. Reset settings
            7. Add 1 node with cinder role
            8. Re-deploy cluster
            9. Run OSTF

        Snapshot: deploy_flat_stop_reset_on_deploying

        """
        if settings.CREATE_ENV:
            self.env.revert_snapshot("ready_with_3_slaves")

        if not cluster_templ.get('release'):
            cluster_templ['release'] = 1

        cluster_templ['deployment_mode']=DEPLOYMENT_MODE_SIMPLE

        with cert_script.make_cluster(self.conn, cluster_templ) as cluster:



            self.fuel_web.provisioning_cluster_wait(
                cluster_id=cluster.id, progress=20)
            try:
                self.fuel_web.stop_deployment_wait(cluster_id)
            except Exception:
                logger.debug(traceback.format_exc())

            self.fuel_web.wait_nodes_get_online_state(self.env.nodes().slaves[:2])
            self.fuel_web.update_nodes(
                cluster_id,
                {
                    'slave-03': ['cinder']
                }
            )



            asserts.assert_equal(
                3, len(self.fuel_web.client.list_cluster_nodes(cluster_id)))

            self.fuel_web.run_ostf(
                cluster_id=cluster_id)
        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_flat_stop_reset_on_provisioning")

    @test(depends_on=[base_test_case.SetupEnvironment.prepare_slaves_3],
          groups=["smoke", "deploy_reset_on_ready"])
    @cluster_template("flat")
    @log_snapshot_on_error
    def deploy_reset_on_ready(self, cluster_templ):
        """Stop reset cluster in simple mode

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Deploy cluster
            5. Reset settings
            6. Update net
            7. Re-deploy cluster
            8. Run OSTF

        Snapshot: deploy_reset_on_ready

        """
        if settings.CREATE_ENV:
            self.env.revert_snapshot("ready_with_3_slaves")

        if not cluster_templ.get('release'):
            cluster_templ['release'] = 1

        with cert_script.make_cluster(self.conn, cluster_templ) as cluster:

            cluster_id = cluster.id
            node = cluster.nodes.controller[0]
            self.fuel_web.assert_cluster_ready(
                node.name, smiles_count=6, networks_count=1, timeout=300)

            self.fuel_web.stop_reset_env_wait(cluster_id)
            self.fuel_web.wait_nodes_get_online_state(self.env.nodes().slaves[:2])

            self.fuel_web.update_vlan_network_fixed(
                cluster_id, amount=8, network_size=32)
            self.fuel_web.deploy_cluster_wait(cluster_id)
            self.fuel_web.assert_cluster_ready(
                node.name, smiles_count=6, networks_count=8, timeout=300)

            self.fuel_web.verify_network(cluster_id)

            self.fuel_web.run_ostf(
                cluster_id=cluster_id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_reset_on_ready")


@test(groups=["thread_3", "cluster_actions"])
class EnvironmentActionOnHA(base_test_case.TestBasic):

    @test(depends_on=[base_test_case.SetupEnvironment.prepare_slaves_5],
          groups=["smoke", "deploy_stop_reset_on_ha"])
    @log_snapshot_on_error
    @cluster_template("ha3controllers")
    def deploy_stop_reset_on_ha(self, cluster_templ):
        """Stop reset cluster in ha mode

        Scenario:
            1. Create cluster
            2. Add 3 node with controller role
            3. Deploy cluster
            4. Stop deployment
            5. Reset settings
            6. Add 2 nodes with compute role
            7. Re-deploy cluster
            8. Run OSTF

        Snapshot: deploy_stop_reset_on_ha

        """
        if settings.CREATE_ENV:
            self.env.revert_snapshot("ready_with_3_slaves")

        if not cluster_templ.get('release'):
            cluster_templ['release'] = 1

        with cert_script.make_cluster(self.conn, cluster_templ) as cluster:
            self.fuel_web.deploy_cluster_wait_progress(cluster_id, progress=10)
            self.fuel_web.stop_deployment_wait(cluster_id)
            self.fuel_web.wait_nodes_get_online_state(self.env.nodes().slaves[:3])
            self.fuel_web.update_nodes(
                cluster_id,
                {
                    'slave-04': ['compute'],
                    'slave-05': ['compute']
                }
            )

            self.fuel_web.deploy_cluster_wait(cluster_id)
            self.fuel_web.assert_cluster_ready(
                'slave-01', smiles_count=16, networks_count=1, timeout=300)

            self.fuel_web.verify_network(cluster_id)

            self.fuel_web.run_ostf(
                cluster_id=cluster.id,
                test_sets=['ha', 'smoke', 'sanity'])
            if settings.CREATE_ENV:
                self.env.make_snapshot("deploy_stop_reset_on_ha")
