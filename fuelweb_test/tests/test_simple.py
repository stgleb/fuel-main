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

from devops.helpers.helpers import wait
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_true
from proboscis import test

from fuelweb_test.helpers import checkers
from devops.helpers.helpers import tcp_ping
from fuelweb_test.helpers.decorators import log_snapshot_on_error
from fuelweb_test.helpers.eb_tables import Ebtables
from fuelweb_test.helpers import os_actions
from fuelweb_test.settings import NODE_VOLUME_SIZE
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic
from fuelweb_test import logger, settings

from fuelweb_test.tests.base_test_case import revert_snapshot
from fuelweb_test.tests.base_test_case import bootstrap_nodes
from fuelweb_test.tests.base_test_case import cluster_template
from certification_script import cert_script


@test(groups=["thread_2"])
class OneNodeDeploy(TestBasic):
    @test(depends_on=[SetupEnvironment.prepare_release],
          groups=["deploy_one_node", "baremetal", "certification"])
    @revert_snapshot("ready")
    @bootstrap_nodes("1")
    @cert_script.with_cluster("simple", release=1)
    def deploy_one_node(self, cluster):
        """Deploy cluster with controller node only

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Deploy the cluster
            4. Validate cluster was set up correctly, there are no dead
            services, there are no errors in logs

        """
        node = cluster.nodes.controller[0]
        self.fuel_web.assert_cluster_ready(node.name,
                                           ip=node.get_ip(),
                                           smiles_count=4,
                                           networks_count=1, timeout=300)
        self.fuel_web.run_single_ostf_test(
            cluster_id=cluster.id, test_sets=['sanity'],
            test_name=('fuel_health.tests.sanity.test_sanity_identity'
                       '.SanityIdentityTest.test_list_users'))


@test(groups=["thread_2"])
class SimpleFlat(TestBasic):
    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["smoke", "deploy_simple_flat", "simple_nova_flat",
                  "baremetal"])
    @log_snapshot_on_error
    @revert_snapshot("ready_with_3_slaves")
    @cert_script.with_cluster("flat", release=1, tear_down=False)
    def deploy_simple_flat(self, cluster):
        """Deploy cluster in simple mode with flat nova-network

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Deploy the cluster
            5. Validate cluster was set up correctly, there are no dead
            services, there are no errors in logs
            6. Verify networks
            7. Verify network configuration on controller
            8. Run OSTF

        Snapshot: deploy_simple_flat

        """
        node = cluster.nodes.controller[0]
        ip = node.get_ip()
        self.fuel_web.assert_cluster_ready(node.name, ip=ip,
                                           smiles_count=6,
                                           networks_count=1, timeout=300)
        self.fuel_web.check_fixed_network_cidr(
            cluster.id, self.env.get_ssh_to_remote(ip))

        self.fuel_web.verify_network(cluster.id)

        checkers.verify_network_configuration(
            node=node,
            remote=self.env.get_ssh_to_remote(ip)
        )

        self.fuel_web.run_ostf(
            cluster_id=cluster.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_simple_flat", is_make=True)

    @test(groups=["simple_flat_create_instance"])
    @log_snapshot_on_error
    def simple_flat_create_instance(self):
        """Create instance with file injection

         Scenario:
            1. Revert "simple flat" environment
            2. Create instance with file injection
            3. Assert instance was created
            4. Assert file is on instance

        """
        # self.env.revert_snapshot("deploy_simple_flat")
        cluster_id = self.fuel_web.get_last_created_cluster()
        cluster = cert_script.fuel_rest_api.reflect_cluster(
            self.conn, cluster_id)

        data = {
            'tenant': 'novaSimpleFlat',
            'user': 'novaSimpleFlat',
            'password': 'novaSimpleFlat'
        }

        controller = cluster.nodes.controller[0]
        # controller = self.fuel_web.get_nailgun_node_by_name('slave-01')
        os = os_actions.OpenStackActions(controller.get_ip(), data['user'],
                                         data['password'], data['tenant'])

        remote = self.env.get_ssh_to_remote(controller.get_ip())

        remote.execute("echo 'Hello World' > /root/test.txt")
        server_files = {"/root/test.txt": 'Hello World'}
        instance = os.create_server_for_migration(file=server_files)
        floating_ip = os.assign_floating_ip(instance)
        wait(lambda: tcp_ping(floating_ip.ip, 22), timeout=120)
        res = os.execute_through_host(
            remote,
            floating_ip.ip, "sudo cat /root/test.txt")
        assert_true(res == 'Hello World', 'file content is {0}'.format(res))

    @test(depends_on=[],
          groups=["simple_flat_node_deletion", "baremetal2"])
    @revert_snapshot("ready_with_3_slaves")
    @log_snapshot_on_error
    def simple_flat_node_deletion(self):
        """Remove controller from cluster in simple mode with flat nova-network

         Scenario:
            1. Revert "simple flat" environment
            2. Remove compute nodes
            3. Deploy changes
            4. Verify node returns to unallocated pull

        """
        if settings.CREATE_ENV:
            self.env.revert_snapshot("deploy_simple_flat")

        cluster_id = self.fuel_web.get_last_created_cluster()
        cluster = cert_script.fuel_rest_api.reflect_cluster(self.conn,
                                                            cluster_id)
        compute = cluster.nodes.compute[0]
        nailgun_nodes = self.fuel_web.update_nodes(
            cluster_id, {compute: ['compute']}, False, True, )
        task = self.fuel_web.deploy_cluster(cluster_id)
        self.fuel_web.assert_task_success(task)
        nodes = filter(lambda x: x["pending_deletion"] is True, nailgun_nodes)
        assert_true(
            len(nodes) == 1, "Verify 1 node has pending deletion status"
        )
        wait(
            lambda: self.fuel_web.is_node_discovered(nodes[0]),
            timeout=10 * 60
        )

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["simple_flat_blocked_vlan"])
    @log_snapshot_on_error
    @cluster_template("flat")
    def simple_flat_blocked_vlan(self, cluster_templ):
        """Verify network verification with blocked VLANs

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Deploy the cluster
            5. Validate cluster was set up correctly, there are no dead
            services, there are no errors in logs
            6. Block first VLAN
            7. Run Verify network and assert it fails
            8. Restore first VLAN

        """
        if settings.CREATE_ENV:
            self.env.revert_snapshot("ready_with_3_slaves")
        if not cluster_templ.get('release'):
            cluster_templ['release'] = 1
        with cert_script.make_cluster(self.conn, cluster_templ) as cluster:
            cluster_id = cluster.id
            node = cluster.nodes.controller[0]
            ip = node.get_ip()
            self.fuel_web.assert_cluster_ready(node.name, ip=ip,
                                               smiles_count=6,
                                               networks_count=1, timeout=300)

            ebtables = self.env.get_ebtables(
                cluster_id, self.env.nodes().slaves[:2])
            ebtables.restore_vlans()
            try:
                ebtables.block_first_vlan()
                self.fuel_web.verify_network(cluster_id, success=False)
            finally:
                ebtables.restore_first_vlan()

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["simple_flat_add_compute", "baremetal"])
    @log_snapshot_on_error
    @cert_script.with_cluster("flat", release=1)
    def simple_flat_add_compute(self, cluster_obj):
        """Add compute node to cluster in simple mode

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Deploy the cluster
            5. Validate cluster was set up correctly, there are no dead
            services, there are no errors in logs
            6. Add 1 node with role compute
            7. Deploy changes
            8. Validate cluster was set up correctly, there are no dead
            services, there are no errors in logs
            9. Verify services list on compute nodes
            10. Run OSTF

        Snapshot: simple_flat_add_compute

        """

        if settings.CREATE_ENV:
            self.env.revert_snapshot("ready_with_3_slaves")

        node = cluster_obj.nodes.controller[0]
        for iface in node.meta['interfaces']:
            ip = iface['ip']
            if ip.startswith('172'):
                break
        self.fuel_web.assert_cluster_ready(node.name, ip=ip,
                                           smiles_count=6,
                                           networks_count=1, timeout=300)
        self.fuel_web.check_fixed_network_cidr(
            cluster_obj.id, self.env.get_ssh_to_remote(ip))

        self.fuel_web.verify_network(cluster_obj.id)

        checkers.verify_network_configuration(
            node=node,
            remote=self.env.get_ssh_to_remote(ip)
        )

        self.fuel_web.run_ostf(
            cluster_id=cluster_obj.id)

        # need to get unallocated nodes and add to cluster

        #new_node = None
        #if new_node:
        #    self.fuel_web.deploy_cluster_wait(cluster_id)
        #
        #    assert_equal(
        #        3, len(self.fuel_web.client.list_cluster_nodes(cluster_id)))
        #
        #    self.fuel_web.assert_cluster_ready(
        #        "slave-01", smiles_count=8, networks_count=1, timeout=300)
        #    self.env.verify_node_service_list("slave-02", 8)
        #    self.env.verify_node_service_list("slave-03", 8)
        #
        #    self.fuel_web.run_ostf(
        #        cluster_id=cluster_id)
        #
        #    self.env.make_snapshot("simple_flat_add_compute")


@test(groups=["thread_2"])
class SimpleVlan(TestBasic):
    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_simple_vlan", "simple_nova_vlan", "certification"])
    @revert_snapshot("ready_with_3_slaves")
    @log_snapshot_on_error
    @cluster_template("simple_vlan")
    @cert_script.with_cluster("simple_vlan", release=1)
    def deploy_simple_vlan(self, cluster):
        """Deploy cluster in simple mode with nova-network VLAN Manager

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Set up cluster to use Network VLAN manager with 8 networks
            5. Deploy the cluster
            6. Validate cluster was set up correctly, there are no dead
            services, there are no errors in logs
            7. Run network verification
            8. Run OSTF

        Snapshot: deploy_simple_vlan

        """
        cluster_id = cluster.id
        self.fuel_web.update_vlan_network_fixed(
            cluster_id, amount=8, network_size=32)
        self.fuel_web.deploy_cluster_wait(cluster_id)
        node = cluster.nodes.controller[0]
        self.fuel_web.assert_cluster_ready(
            node.name, smiles_count=6, networks_count=8, timeout=300)

        self.fuel_web.verify_network(cluster.id)

        self.fuel_web.run_ostf(
            cluster_id=cluster.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_simple_vlan", is_make=True)


@test(groups=["thread_2", "multirole"])
class MultiroleControllerCinder(TestBasic):
    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_multirole_controller_cinder", "certification"])
    @log_snapshot_on_error
    @cluster_template("multirolecontroller")
    @cert_script.with_cluster("multirolecontroller", release=1)
    def deploy_multirole_controller_cinder(self, cluster):
        """Deploy cluster in simple mode with multi-role controller and cinder

        Scenario:
            1. Create cluster
            2. Add 1 node with controller and cinder roles
            3. Add 1 node with compute role
            4. Deploy the cluster
            5. Run network verification
            6. Run OSTF

        Snapshot: deploy_multirole_controller_cinder

        """
        self.fuel_web.verify_network(cluster.id)
        self.fuel_web.run_ostf(
            cluster_id=cluster.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_multirole_controller_cinder")


@test(groups=["thread_2", "multirole"])
class MultiroleComputeCinder(TestBasic):
    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_multirole_compute_cinder", "certification"])
    @log_snapshot_on_error
    @cluster_template("multirolecompute")
    @cert_script.with_cluster("multirolecompute", release=1)
    def deploy_multirole_compute_cinder(self, cluster):
        """Deploy cluster in simple mode with multi-role compute and cinder

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 2 node with compute and cinder roles
            4. Deploy the cluster
            5. Run network verification
            6. Run OSTF

        Snapshot: deploy_multirole_compute_cinder

        """
        self.fuel_web.verify_network(cluster.id)
        self.fuel_web.run_ostf(
            cluster_id=cluster.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_multirole_compute_cinder")


@test(groups=["thread_2"])
class FloatingIPs(TestBasic):
    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_floating_ips", "certification"])
    @log_snapshot_on_error
    @revert_snapshot("ready_with_3_slaves")
    @cluster_template("simplefloatingip")
    @cert_script.with_cluster("simplefloatingip", release=1)
    def deploy_floating_ips(self, cluster):
        """Deploy cluster with non-default 3 floating IPs ranges

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute and cinder roles
            4. Update floating IP ranges. Use 3 ranges
            5. Deploy the cluster
            6. Verify available floating IP list
            7. Run OSTF

        Snapshot: deploy_floating_ips

        """
        cluster_id = cluster.id
        networking_parameters = {
            "floating_ranges": self.fuel_web.get_floating_ranges()[0]}

        self.fuel_web.client.update_network(
            cluster_id,
            networking_parameters=networking_parameters
        )

        # assert ips
        compute = cluster.nodes["compute"]
        expected_ips = self.fuel_web.get_floating_ranges()[1]
        self.fuel_web.assert_cluster_floating_list(compute.name, expected_ips)

        self.fuel_web.run_ostf(
            cluster_id=cluster_id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_floating_ips")


@test(groups=["simple_cinder"])
class SimpleCinder(TestBasic):
    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_simple_cinder", "simple_nova_cinder",
                  "certification"])
    @log_snapshot_on_error
    @cluster_template("simplecinder")
    @cert_script.with_cluster("simplecinder", release=1)
    def deploy_simple_cinder(self, cluster):
        """Deploy cluster in simple mode with cinder

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Add 1 node with cinder role
            5. Deploy the cluster
            6. Validate cluster was set up correctly, there are no dead
            services, there are no errors in logs
            7. Run OSTF

        Snapshot: deploy_simple_cinder

        """
        self.fuel_web.verify_network(cluster.id)

        node = cluster.nodes.controller[0]
        ip = node.get_ip()

        checkers.verify_network_configuration(
            node=node,
            remote=self.env.get_ssh_to_remote(ip)
        )

        self.fuel_web.assert_cluster_ready(
            node.name, ip=ip, smiles_count=6, networks_count=1, timeout=300)
        self.fuel_web.check_fixed_network_cidr(
            cluster.id, self.env.get_ssh_to_remote(ip))

        self.fuel_web.run_ostf(
            cluster_id=cluster.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_simple_cinder")


@test(groups=["thread_1", "gleb4"])
class NodeMultipleInterfaces(TestBasic):
    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_node_multiple_interfaces"])
    @log_snapshot_on_error
    @revert_snapshot("ready_with_3_slaves")
    @cluster_template("deploy_node_multiple_interfaces")
    @cert_script.with_cluster("deploy_node_multiple_interfaces", release=1)
    def deploy_node_multiple_interfaces(self, cluster_obj):
        """Deploy cluster with networks allocated on different interfaces

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Add 1 node with cinder role
            5. Split networks on existing physical interfaces
            6. Deploy the cluster
            7. Verify network configuration on each deployed node
            8. Run network verification

        Snapshot: deploy_node_multiple_interfaces

        """
        cluster = self.fuel_web.client.get_cluster(cluster_obj.id)
        for node in cluster.nodes:
            self.env.verify_network_configuration(node)

        self.fuel_web.verify_network(cluster.id)

        if settings.CREATE_ENV:
            self.env.make_snapshot("deploy_node_multiple_interfaces")


@test(groups=["thread_1"])
class NodeDiskSizes(TestBasic):
    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["check_nodes_notifications"])
    @revert_snapshot("ready_with_3_slaves")
    @log_snapshot_on_error
    def check_nodes_notifications(self):
        """Verify nailgun notifications for discovered nodes

        Scenario:
            1. Revert snapshot "ready_with_3_slaves"
            2. Verify hard drive sizes for discovered nodes in /api/nodes
            3. Verify hard drive sizes for discovered nodes in notifications

        """

        # assert /api/nodes
        disk_size = NODE_VOLUME_SIZE * 1024 ** 3
        nailgun_nodes = self.fuel_web.client.list_nodes()
        for node in nailgun_nodes:
            for disk in node['meta']['disks']:
                assert_equal(disk['size'], disk_size, 'Disk size')

        hdd_size = "{} TB HDD".format(float(disk_size * 3 / (10 ** 9)) / 1000)
        notifications = self.fuel_web.client.get_notifications()
        for node in nailgun_nodes:
            # assert /api/notifications
            for notification in notifications:
                discover = notification['topic'] == 'discover'
                current_node = notification['node_id'] == node['id']
                if current_node and discover and \
                   "discovered" in notification['message']:
                    assert_true(hdd_size in notification['message'])

            # assert disks
            disks = self.fuel_web.client.get_node_disks(node['id'])
            for disk in disks:
                assert_equal(disk['size'],
                             NODE_VOLUME_SIZE * 1024 - 500, 'Disk size')

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["check_nodes_disks", "rem"])
    @revert_snapshot("ready_with_3_slaves")
    @cluster_template("check_nodes_disks")
    @cert_script.with_cluster("check_nodes_disks", release=1)
    @log_snapshot_on_error
    def check_nodes_disks(self, cluster):
        """Verify nailgun notifications for discovered nodes

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Add 1 node with cinder role
            5. Deploy the cluster
            6. Verify hard drive sizes for deployed nodes

        """
        cluster_id = cluster.id
        self.fuel_web.run_ostf(cluster_id=cluster_id)
        nodes = cluster.nodes

        nodes_dict = {}

        for node in nodes:
            nodes_dict[node.name] = node.roles

        # assert node disks after deployment
        for node_name in nodes_dict:
            str_block_devices = self.fuel_web.get_cluster_block_devices(
                node_name)

            logger.debug("Block device:\n{}".format(str_block_devices))

            expected_regexp = re.compile(
                "vda\s+\d+:\d+\s+0\s+{}G\s+0\s+disk".format(NODE_VOLUME_SIZE))
            assert_true(
                expected_regexp.search(str_block_devices),
                "Unable to find vda block device for {}G in: {}".format(
                    NODE_VOLUME_SIZE, str_block_devices
                ))

            expected_regexp = re.compile(
                "vdb\s+\d+:\d+\s+0\s+{}G\s+0\s+disk".format(NODE_VOLUME_SIZE))
            assert_true(
                expected_regexp.search(str_block_devices),
                "Unable to find vdb block device for {}G in: {}".format(
                    NODE_VOLUME_SIZE, str_block_devices
                ))

            expected_regexp = re.compile(
                "vdc\s+\d+:\d+\s+0\s+{}G\s+0\s+disk".format(NODE_VOLUME_SIZE))
            assert_true(
                expected_regexp.search(str_block_devices),
                "Unable to find vdc block device for {}G in: {}".format(
                    NODE_VOLUME_SIZE, str_block_devices
                ))


@test(groups=["thread_1"])
class MultinicBootstrap(TestBasic):
    @test(depends_on=[SetupEnvironment.prepare_release],
          groups=["multinic_bootstrap_booting"])
    @revert_snapshot("ready")
    @log_snapshot_on_error
    def multinic_bootstrap_booting(self):
        """Verify slaves booting with blocked mac address

        Scenario:
            1. Revert snapshot "ready"
            2. Block traffic for first slave node (by mac)
            3. Restore mac addresses and boot first slave
            4. Verify slave mac addresses is equal to unblocked

        """
        slave = self.env.nodes().slaves[0]
        mac_addresses = [interface.mac_address for interface in
                         slave.interfaces.filter(network__name='internal')]
        try:
            for mac in mac_addresses:
                Ebtables.block_mac(mac)
            for mac in mac_addresses:
                Ebtables.restore_mac(mac)
                slave.destroy(verbose=False)
                self.env.nodes().admins[0].revert("ready")
                nailgun_slave = self.env.bootstrap_nodes([slave])[0]
                assert_equal(mac.upper(), nailgun_slave['mac'].upper())
                Ebtables.block_mac(mac)
        finally:
            for mac in mac_addresses:
                Ebtables.restore_mac(mac)


@test(groups=["thread_2", "delete_env", "rem"])
class DeleteEnvironment(TestBasic):
    @test(depends_on=[SimpleFlat.deploy_simple_flat],
          groups=["delete_environment"])
    @revert_snapshot("ready_with_3_slaves")
    @log_snapshot_on_error
    def delete_environment(self):
        """Delete existing environment
        and verify nodes returns to unallocated state

        Scenario:
            1. Revert "simple flat" environment
            2. Delete environment
            3. Verify node returns to unallocated pull

        """

        cluster_id = self.fuel_web.get_last_created_cluster()
        cluster = cert_script.fuel_rest_api.reflect_cluster(
            self.conn, cluster_id)
        cluster.delete()
        nailgun_nodes = self.fuel_web.client.list_nodes()
        nodes = filter(lambda x: x["pending_deletion"] is True, nailgun_nodes)
        assert_true(
            len(nodes) == 2, "Verify 2 node has pending deletion status"
        )
        wait(
            lambda:
            self.fuel_web.is_node_discovered(nodes[0]) and
            self.fuel_web.is_node_discovered(nodes[1]),
            timeout=10 * 60,
            interval=15
        )


@test(groups=["thread_1", "untagged_networks_negative"])
class UntaggedNetworksNegative(TestBasic):
    @test(
        depends_on=[SetupEnvironment.prepare_slaves_3],
        groups=["untagged_networks_negative"],
        enabled=False)
    @log_snapshot_on_error
    @cluster_template("untagged_networks_negative")
    @cert_script.with_cluster("untagged_networks_negative", release=1)
    def untagged_networks_negative(self, cluster_obj):
        """Verify network verification fails with untagged network on eth0

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Split networks on existing physical interfaces
            5. Remove VLAN tagging from networks which are on eth0
            6. Run network verification (assert it fails)
            7. Start cluster deployment (assert it fails)

        """
        vlan_turn_off = {'vlan_start': None}
        nets = self.fuel_web.client.get_networks(cluster_obj.id)['networks']
        # select networks that will be untagged:
        for net in nets:
            net.update(vlan_turn_off)

        # stop using VLANs:
        self.fuel_web.client.update_network(cluster_obj.id, networks=nets)

        # run network check:
        self.fuel_web.verify_network(cluster_obj.id, success=False)

        # deploy cluster:
        task = self.fuel_web.deploy_cluster(cluster_obj.id)
        self.fuel_web.assert_task_failed(task)


@test(groups=["known_issues", "gleb_test"])
class BackupRestoreSimple(TestBasic):
    @test(depends_on=[SimpleFlat.deploy_simple_flat],
          groups=["simple_backup_restore"])
    @log_snapshot_on_error
    def simple_backup_restore(self):
        """Backup/restore master node with cluster in simple mode

        Scenario:
            1. Revert snapshot "deploy_simple_flat"
            2. Backup master
            3. Check backup
            4. Run OSTF
            5. Add 1 node with compute role
            6. Restore master
            7. Check restore
            8. Run OSTF

        """
        self.env.revert_snapshot("deploy_simple_flat")

        cluster_id = self.fuel_web.get_last_created_cluster()
        self.fuel_web.assert_cluster_ready(
            'slave-01', smiles_count=6, networks_count=1, timeout=300)
        self.fuel_web.backup_master(self.env.get_admin_remote())
        checkers.backup_check(self.env.get_admin_remote())

        self.fuel_web.update_nodes(
            cluster_id, {'slave-03': ['compute']}, True, False)

        assert_equal(
            3, len(self.fuel_web.client.list_cluster_nodes(cluster_id)))

        self.fuel_web.restore_master(self.env.get_admin_remote())
        checkers.restore_check_sum(self.env.get_admin_remote())
        self.fuel_web.restore_check_nailgun_api(self.env.get_admin_remote())
        checkers.iptables_check(self.env.get_admin_remote())

        assert_equal(
            2, len(self.fuel_web.client.list_cluster_nodes(cluster_id)))

        self.fuel_web.update_nodes(
            cluster_id, {'slave-03': ['compute']}, True, False)
        self.fuel_web.deploy_cluster_wait(cluster_id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_id)

        self.env.make_snapshot("simple_backup_restore")
