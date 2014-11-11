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

from proboscis.asserts import assert_equal
from proboscis import test
from fuelweb_test import settings

from fuelweb_test.helpers.decorators import log_snapshot_on_error
from fuelweb_test.settings import DEPLOYMENT_MODE_HA
from fuelweb_test.settings import DEPLOYMENT_MODE_SIMPLE
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic

from fuelweb_test.tests.base_test_case import revert_snapshot
from fuelweb_test.tests.base_test_case import bootstrap_nodes
from fuelweb_test.tests.base_test_case import cluster_template
from certification_script import cert_script

@test(groups=["thread_1", "neutron", "bvt_1"])
class NeutronGre(TestBasic):

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_neutron_gre", "simple_neutron_gre", "gleb2"])
    @revert_snapshot("ready_with_3_slaves")
    @log_snapshot_on_error
    @cert_script.with_cluster("neutron_simple_gre", release=1)
    def deploy_neutron_gre(self, cluster):
        """Deploy cluster in simple mode with Neutron GRE

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 2 nodes with compute role
            4. Deploy the cluster
            5. Run network verification
            6. Run OSTF

        Snapshot deploy_neutron_gre

        """
        self.fuel_web.update_internal_network(cluster.id, '192.168.196.0/26',
                                              '192.168.196.1')
        self.fuel_web.deploy_cluster_wait(cluster.id)

        cluster = self.fuel_web.client.get_cluster(cluster.id)
        assert_equal(str(cluster['net_provider']), 'neutron')
        # assert_equal(str(cluster['net_segment_type']), segment_type)
        self.fuel_web.check_fixed_network_cidr(
            cluster.id, self.env.get_ssh_to_remote_by_name('slave-01'))

        self.fuel_web.verify_network(cluster.id)
        self.fuel_web.security.verify_firewall(cluster.id)

        self.fuel_web.run_ostf(
            cluster_id=cluster.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_neutron_gre")


@test(groups=["thread_1", "neutron"])
class NeutronVlan(TestBasic):

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_neutron_vlan", "simple_neutron_vlan", "gleb"])
    @revert_snapshot("ready_with_3_slaves")
    @log_snapshot_on_error
    @cert_script.with_cluster("neutron_vlan", release=1)
    def deploy_neutron_vlan(self, cluster_obj):
        """Deploy cluster in simple mode with Neutron VLAN

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 2 nodes with compute role
            4. Deploy the cluster
            5. Run network verification
            6. Run OSTF

        Snapshot deploy_neutron_vlan

        """

        self.fuel_web.deploy_cluster_wait(cluster_id)

        cluster = self.fuel_web.client.get_cluster(cluster_obj.id)
        assert_equal(str(cluster['net_provider']), 'neutron')
        # assert_equal(str(cluster['net_segment_type']), segment_type)

        self.fuel_web.verify_network(cluster_obj.id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_obj.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_neutron_vlan")


@test(groups=["thread_4", "neutron", "ha", "ha_neutron", "gleb"])
class NeutronGreHa(TestBasic):

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["deploy_neutron_gre_ha", "ha_neutron_gre"])
    @revert_snapshot("ready_with_5_slaves")
    @log_snapshot_on_error
    @cert_script.with_cluster("neutron_gre_ha")
    def deploy_neutron_gre_ha(self, cluster_obj):
        """Deploy cluster in HA mode with Neutron GRE

        Scenario:
            1. Create cluster
            2. Add 3 nodes with controller role
            3. Add 2 nodes with compute role
            4. Deploy the cluster
            5. Run network verification
            6. Run OSTF

        Snapshot deploy_neutron_gre_ha

        """

        self.fuel_web.deploy_cluster_wait(cluster_id)

        cluster = self.fuel_web.client.get_cluster(cluster_obj.id)
        assert_equal(str(cluster['net_provider']), 'neutron')
        # assert_equal(str(cluster['net_segment_type']), segment_type)

        self.fuel_web.verify_network(cluster_obj.id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_obj.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_neutron_gre_ha")


@test(groups=["thread_6", "neutron", "ha", "ha_neutron", "gleb"])
class NeutronGreHaPublicNetwork(TestBasic):

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["deploy_neutron_gre_ha_public_network"])
    @revert_snapshot("ready_with_5_slaves")
    @log_snapshot_on_error
    @cert_script.with_cluster("neutron_gre_ha_public_networks")
    def deploy_neutron_gre_ha_with_public_network(self, cluster_obj):
        """Deploy cluster in HA mode with Neutron GRE and public network
           assigned to all nodes

        Scenario:
            1. Create cluster
            2. Add 3 nodes with controller role
            3. Add 2 nodes with compute role
            4. Enable assign public networks to all nodes option
            5. Deploy the cluster
            6. Check that public network was assigned to all nodes
            7. Run network verification
            8. Run OSTF

        Snapshot deploy_neutron_gre_ha_public_network

        """

        self.fuel_web.deploy_cluster_wait(cluster_obj.id)

        cluster = self.fuel_web.client.get_cluster(cluster_obj.id)
        assert_equal(str(cluster['net_provider']), 'neutron')
        # assert_equal(str(cluster['net_segment_type']), segment_type)

        self.fuel_web.verify_network(cluster_obj.id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_obj.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_neutron_gre_ha_public_network")


@test(groups=["thread_3", "neutron", "ha", "ha_neutron", "bvt_1", "gleb"])
class NeutronVlanHa(TestBasic):

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["deploy_neutron_vlan_ha", "ha_neutron_vlan"])
    @revert_snapshot("ready_with_5_slaves")
    @log_snapshot_on_error
    @cert_script.with_cluster("neutron_vlan_ha")
    def deploy_neutron_vlan_ha(self, cluster_obj):
        """Deploy cluster in HA mode with Neutron VLAN

        Scenario:
            1. Create cluster
            2. Add 3 nodes with controller role
            3. Add 2 nodes with compute role
            4. Deploy the cluster
            5. Run network verification
            6. Run OSTF

        Snapshot deploy_neutron_vlan_ha

        """
        self.fuel_web.update_internal_network(cluster_obj.id, '192.168.196.0/22',
                                          '192.168.196.1')
        self.fuel_web.deploy_cluster_wait(cluster_obj.id)

        cluster = self.fuel_web.client.get_cluster(cluster_obj.id)
        assert_equal(str(cluster['net_provider']), 'neutron')
        # assert_equal(str(cluster['net_segment_type']), segment_type)
        self.fuel_web.check_fixed_network_cidr(
            cluster_id, self.env.get_ssh_to_remote_by_name('slave-01'))

        self.fuel_web.verify_network(cluster_obj.id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_obj.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_neutron_vlan_ha")


@test(groups=["thread_6", "neutron", "ha", "ha_neutron", "gleb"])
class NeutronVlanHaPublicNetwork(TestBasic):

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["deploy_neutron_vlan_ha_public_network"])
    @revert_snapshot("ready_with_5_slaves")
    @log_snapshot_on_error
    @cert_script.with_cluster("neutron_vlan_ha_public_networks")
    def deploy_neutron_vlan_ha_with_public_network(self, cluster_obj):
        """Deploy cluster in HA mode with Neutron VLAN and public network
           assigned to all nodes

        Scenario:
            1. Create cluster
            2. Add 3 nodes with controller role
            3. Add 2 nodes with compute role
            4. Enable assign public networks to all nodes option
            5. Deploy the cluster
            6. Check that public network was assigned to all nodes
            7. Run network verification
            8. Run OSTF

        Snapshot deploy_neutron_vlan_ha_public_network


    """
        self.fuel_web.update_internal_network(cluster_obj.id, '192.168.196.0/22',
                                              '192.168.196.1')
        self.fuel_web.deploy_cluster_wait(cluster_obj.id)

        cluster = self.fuel_web.client.get_cluster(cluster_obj.id)
        assert_equal(str(cluster['net_provider']), 'neutron')
        # assert_equal(str(cluster['net_segment_type']), segment_type)
        self.fuel_web.check_fixed_network_cidr(
            cluster_obj.id, self.env.get_ssh_to_remote_by_name('slave-01'))

        self.fuel_web.verify_network(cluster_obj.id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_obj.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_neutron_vlan_ha_public_network")
