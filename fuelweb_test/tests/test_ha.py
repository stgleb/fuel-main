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

import re

from proboscis.asserts import assert_equal
from proboscis.asserts import assert_true
from proboscis import test

from fuelweb_test.helpers import checkers
from fuelweb_test.helpers.decorators import log_snapshot_on_error
from fuelweb_test.settings import DEPLOYMENT_MODE_HA
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic

from fuelweb_test.tests.base_test_case import revert_snapshot
from fuelweb_test.tests.base_test_case import bootstrap_nodes
from fuelweb_test.tests.base_test_case import cluster_template
from certification_script import cert_script


@test(groups=["thread_3", "ha", "bvt_2"])
class TestHaVLAN(TestBasic):

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_ha_vlan", "ha_nova_vlan"])
    @revert_snapshot("ready_with_5_slaves")
    @log_snapshot_on_error
    @cluster_template("nova_ha_vlan")
    @cert_script.with_cluster("nova_ha_vlan", release=1)
    def deploy_ha_vlan(self, cluster):
        """Deploy cluster in HA mode with VLAN Manager

        Scenario:
            1. Create cluster
            2. Add 3 nodes with controller roles
            3. Add 2 nodes with compute roles
            4. Set up cluster to use Network VLAN manager with 8 networks
            5. Deploy the cluster
            6. Validate cluster was set up correctly, there are no dead
            services, there are no errors in logs
            7. Run network verification
            8. Run OSTF
            9. Create snapshot

        Snapshot deploy_ha_vlan

        """
        cluster_id = cluster.id

        self.fuel_web.update_vlan_network_fixed(
            cluster_id, amount=8, network_size=32
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)
        self.fuel_web.assert_cluster_ready(
            'slave-01', smiles_count=16, networks_count=8, timeout=300)

        #self.fuel_web.check_fixed_network_cidr(
        #    cluster_id, self.env.get_ssh_to_remote_by_name('slave-01'))
        self.fuel_web.verify_network(cluster_id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_id,
            test_sets=['ha', 'smoke', 'sanity'])

        self.env.make_snapshot("deploy_ha_vlan")


@test(groups=["thread_4", "ha"])
class TestHaFlat(TestBasic):

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["deploy_ha_flat", "ha_nova_flat"])
    @log_snapshot_on_error
    @revert_snapshot("ready_with_5_slaves")
    @log_snapshot_on_error
    @cluster_template("nova_ha_flat")
    @cert_script.with_cluster("nova_ha_flat", release=1)
    def deploy_ha_flat(self, cluster):
        """Deploy cluster in HA mode with flat nova-network

        Scenario:
            1. Create cluster
            2. Add 3 nodes with controller roles
            3. Add 2 nodes with compute roles
            4. Deploy the cluster
            5. Validate cluster was set up correctly, there are no dead
            services, there are no errors in logs
            6. Run verify networks
            7. Run OSTF
            8. Make snapshot

        Snapshot deploy_ha_flat

        """
        self.fuel_web.deploy_cluster_wait(cluster_id)
        self.fuel_web.assert_cluster_ready(
            'slave-01', smiles_count=16, networks_count=1, timeout=300)

        self.fuel_web.verify_network(cluster_id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_id,
            test_sets=['ha', 'smoke', 'sanity'])

        self.env.make_snapshot("deploy_ha_flat")


@test(groups=["thread_4", "ha", "gleb8"])
class TestHaFlatAddCompute(TestBasic):

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["ha_flat_add_compute"])
    @log_snapshot_on_error
    @revert_snapshot("ready_with_3_slaves")
    @cluster_template("test_ha_flat_add_compute")
    @cert_script.with_cluster("test_ha_flat_add_compute", release=1)
    def ha_flat_add_compute(self, cluster):
        """Add compute node to cluster in HA mode with flat nova-network

        Scenario:
            1. Create cluster
            2. Add 3 nodes with controller roles
            3. Add 2 nodes with compute roles
            4. Deploy the cluster
            5. Validate cluster was set up correctly, there are no dead
            services, there are no errors in logs
            6. Add 1 node with compute role
            7. Deploy the cluster
            8. Run network verification
            9. Run OSTF

        Snapshot ha_flat_add_compute

        """
        cluster_id = cluster.id
        self.fuel_web.deploy_cluster_wait(cluster_id)
        self.fuel_web.assert_cluster_ready(
            'slave-01', smiles_count=16, networks_count=1, timeout=300)

        self.env.bootstrap_nodes(self.env.nodes().slaves[5:6])
        self.fuel_web.update_nodes(
            cluster_id, {'slave-03': ['compute']}, True, False
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)

        self.fuel_web.verify_network(cluster_id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_id,
            test_sets=['ha', 'smoke', 'sanity'])

        self.env.make_snapshot("ha_flat_add_compute")


@test(groups=["thread_4", "ha", "gleb8"])
class TestHaFlatScalability(TestBasic):

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["ha_flat_scalability", "ha_nova_flat_scalability"])
    @log_snapshot_on_error
    @revert_snapshot("ready_with_3_slaves")
    @cluster_template("ha_flat_scalability")
    @cert_script.with_cluster("ha_flat_scalability", release=1)
    def ha_flat_scalability(self):
        """Check HA mode on scalability

        Scenario:
            1. Create cluster
            2. Add 1 controller node
            3. Deploy the cluster
            4. Add 2 controller nodes
            5. Deploy changes
            6. Run network verification
            7. Add 2 controller nodes
            8. Deploy changes
            9. Run network verification
            10. Run OSTF

        Snapshot ha_flat_scalability

        """
        self.fuel_web.deploy_cluster_wait(cluster_id)

        self.fuel_web.update_nodes(
            cluster_id, {'slave-02': ['controller'],
                         'slave-03': ['controller']},
            True, False
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)
        for devops_node in self.env.nodes().slaves[:3]:
            self.fuel_web.assert_pacemaker(
                devops_node.name, self.env.nodes().slaves[:3], [])

        self.fuel_web.update_nodes(
            cluster_id, {'slave-04': ['controller'],
                         'slave-05': ['controller']},
            True, False
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)
        for devops_node in self.env.nodes().slaves[:5]:
            ret = self.fuel_web.get_pacemaker_status(devops_node.name)
            assert_true(
                re.search('vip__management\s+\(ocf::mirantis:ns_IPaddr2\):'
                          '\s+Started node', ret), 'vip management started')
            assert_true(
                re.search('vip__public\s+\(ocf::mirantis:ns_IPaddr2\):'
                          '\s+Started node', ret), 'vip public started')
        self.fuel_web.run_ostf(
            cluster_id=cluster_id,
            test_sets=['ha', 'sanity'])

        self.env.make_snapshot("ha_flat_scalability")


@test(groups=["known_issues", "ha", "gleb8"])
class BackupRestoreHa(TestBasic):

    @test(depends_on=[TestHaFlat.deploy_ha_flat],
          groups=["known_issues", "backup_restore_ha_flat"])
    @log_snapshot_on_error
    def backup_restore_ha_flat(self):
        """Backup/restore master node with cluster in ha mode

        Scenario:
            1. Revert snapshot "deploy_ha_flat"
            2. Backup master
            3. Check backup
            4  Run OSTF
            5. Add 1 node with compute role
            6. Restore master
            7. Check restore
            8. Run OSTF

        """
        self.env.revert_snapshot("deploy_ha_flat")

        cluster_id = self.fuel_web.get_last_created_cluster()
        self.fuel_web.assert_cluster_ready(
            'slave-01', smiles_count=16, networks_count=1, timeout=300)
        self.fuel_web.backup_master(self.env.get_admin_remote())
        checkers.backup_check(self.env.get_admin_remote())
        self.env.bootstrap_nodes(self.env.nodes().slaves[5:6])
        self.fuel_web.update_nodes(
            cluster_id, {'slave-06': ['compute']}, True, False
        )

        assert_equal(
            6, len(self.fuel_web.client.list_cluster_nodes(cluster_id)))

        self.fuel_web.restore_master(self.env.get_admin_remote())
        checkers.restore_check_sum(self.env.get_admin_remote())
        self.fuel_web.restore_check_nailgun_api(self.env.get_admin_remote())
        checkers.iptables_check(self.env.get_admin_remote())

        assert_equal(
            5, len(self.fuel_web.client.list_cluster_nodes(cluster_id)))

        self.env.bootstrap_nodes(self.env.nodes().slaves[5:6])
        self.fuel_web.update_nodes(
            cluster_id, {'slave-06': ['compute']}, True, False
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_id,
            test_sets=['ha', 'smoke', 'sanity'])

        self.env.make_snapshot("backup_restore_ha_flat")
