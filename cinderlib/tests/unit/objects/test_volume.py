# Copyright (c) 2018, Red Hat, Inc.
# All Rights Reserved.
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

import mock

from cinderlib import exception
from cinderlib import objects
from cinderlib.tests.unit import base


class TestVolume(base.BaseTest):
    def test_init_from_args_backend_name(self):
        vol = objects.Volume(self.backend_name,
                             name='vol_name', description='vol_desc', size=10)
        self.assertEqual(self.backend, vol.backend)
        self.assertEqual('vol_name', vol.name)
        self.assertEqual('vol_name', vol.display_name)
        self.assertEqual('vol_desc', vol.description)
        self.assertEqual(10, vol.size)
        self.assertIsNotNone(vol.id)

    def test_init_from_args_backend(self):
        vol = objects.Volume(self.backend,
                             name='vol_name', description='vol_desc', size=10)
        self.assertEqual(self.backend, vol.backend)
        self.assertEqual('vol_name', vol.name)
        self.assertEqual('vol_name', vol.display_name)
        self.assertEqual('vol_desc', vol.description)
        self.assertEqual(10, vol.size)
        self.assertIsNotNone(vol.id)

    def test_init_from_volume(self):
        vol = objects.Volume(self.backend,
                             name='vol_name', description='vol_desc', size=10)
        vol2 = objects.Volume(vol, name='new_name', size=11)
        self.assertEqual(self.backend, vol2.backend)
        self.assertEqual('new_name', vol2.name)
        self.assertEqual('new_name', vol2.display_name)
        self.assertEqual(vol.description, vol2.description)
        self.assertEqual(11, vol2.size)
        self.assertIsNotNone(vol2.id)
        self.assertNotEqual(vol.id, vol2.id)

    def test_init_from_ovo(self):
        vol = objects.Volume(self.backend, size=10)
        vol2 = objects.Volume(self.backend, __ovo=vol._ovo)
        self.assertEqual(vol._ovo, vol2._ovo)

    def test_snapshots_lazy_loading(self):
        vol = objects.Volume(self.backend, size=10)
        vol._snapshots = None

        snaps = [objects.Snapshot(vol, name='my_snap')]
        # Persistence retrieves Snapshots without the Volume, just volume_id
        snaps[0]._ovo.volume = None

        mock_get_snaps = self.persistence.get_snapshots
        mock_get_snaps.return_value = snaps

        result = vol.snapshots

        mock_get_snaps.called_once_with(vol.id)
        self.assertEqual(snaps, result)
        self.assertEqual(snaps, vol._snapshots)
        self.assertEqual(1, len(vol._ovo.snapshots))
        self.assertEqual(vol._ovo.snapshots[0], result[0]._ovo)
        # There is no second call when we reference it again
        mock_get_snaps.reset_mock()
        result = vol.snapshots
        self.assertEqual(snaps, result)
        mock_get_snaps.not_called()

    def test_connections_lazy_loading(self):
        vol = objects.Volume(self.backend, size=10)
        vol._connections = None

        conns = [objects.Connection(self.backend, connector={'k': 'v'},
                                    volume_id=vol.id, status='attached',
                                    attach_mode='rw',
                                    connection_info={'conn': {}},
                                    name='my_snap')]

        mock_get_conns = self.persistence.get_connections
        mock_get_conns.return_value = conns

        result = vol.connections

        mock_get_conns.called_once_with(volume_id=vol.id)
        self.assertEqual(conns, result)
        self.assertEqual(conns, vol._connections)
        self.assertEqual(1, len(vol._ovo.volume_attachment))
        self.assertEqual(vol._ovo.volume_attachment[0], result[0]._ovo)
        # There is no second call when we reference it again
        mock_get_conns.reset_mock()
        result = vol.connections
        self.assertEqual(conns, result)
        mock_get_conns.not_called()

    def test_get_by_id(self):
        mock_get_vols = self.persistence.get_volumes
        mock_get_vols.return_value = [mock.sentinel.vol]
        res = objects.Volume.get_by_id(mock.sentinel.vol_id)
        mock_get_vols.assert_called_once_with(volume_id=mock.sentinel.vol_id)
        self.assertEqual(mock.sentinel.vol, res)

    def test_get_by_id_not_found(self):
        mock_get_vols = self.persistence.get_volumes
        mock_get_vols.return_value = None
        self.assertRaises(exception.VolumeNotFound,
                          objects.Volume.get_by_id, mock.sentinel.vol_id)
        mock_get_vols.assert_called_once_with(volume_id=mock.sentinel.vol_id)

    def test_get_by_name(self):
        res = objects.Volume.get_by_name(mock.sentinel.name)
        mock_get_vols = self.persistence.get_volumes
        mock_get_vols.assert_called_once_with(volume_name=mock.sentinel.name)
        self.assertEqual(mock_get_vols.return_value, res)

    def test_create(self):
        self.backend.driver.create_volume.return_value = None
        vol = self.backend.create_volume(10, name='vol_name',
                                         description='des')
        self.backend.driver.create_volume.assert_called_once_with(vol._ovo)
        self.assertEqual('available', vol.status)
        self.persistence.set_volume.assert_called_once_with(vol)

    def test_create_error(self):
        self.backend.driver.create_volume.side_effect = exception.NotFound
        with self.assertRaises(exception.NotFound) as assert_context:
            self.backend.create_volume(10, name='vol_name', description='des')
        vol = assert_context.exception.resource
        self.assertIsInstance(vol, objects.Volume)
        self.assertEqual(10, vol.size)
        self.assertEqual('vol_name', vol.name)
        self.assertEqual('des', vol.description)

    def test_delete(self):
        vol = objects.Volume(self.backend_name, size=10)
        vol.delete()
        self.backend.driver.delete_volume.assert_called_once_with(vol._ovo)
        self.persistence.delete_volume.assert_called_once_with(vol)
        self.assertEqual('deleted', vol.status)

    def test_delete_error_with_snaps(self):
        vol = objects.Volume(self.backend_name, size=10, status='available')
        snap = objects.Snapshot(vol)
        vol._snapshots.append(snap)
        self.assertRaises(exception.InvalidVolume, vol.delete)
        self.assertEqual('available', vol.status)

    def test_delete_error(self):
        vol = objects.Volume(self.backend_name,
                             name='vol_name', description='vol_desc', size=10)
        self.backend.driver.delete_volume.side_effect = exception.NotFound
        with self.assertRaises(exception.NotFound) as assert_context:
            vol.delete()

        self.assertEqual(vol, assert_context.exception.resource)
        self.backend.driver.delete_volume.assert_called_once_with(vol._ovo)
        self.assertEqual('error_deleting', vol.status)

    def test_extend(self):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        vol.extend(11)

        self.backend.driver.extend_volume.assert_called_once_with(vol._ovo, 11)
        self.persistence.set_volume.assert_called_once_with(vol)
        self.assertEqual('available', vol.status)
        self.assertEqual(11, vol.size)

    def test_extend_error(self):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        self.backend.driver.extend_volume.side_effect = exception.NotFound
        with self.assertRaises(exception.NotFound) as assert_context:
            vol.extend(11)

        self.assertEqual(vol, assert_context.exception.resource)
        self.backend.driver.extend_volume.assert_called_once_with(vol._ovo, 11)
        self.persistence.set_volume.assert_called_once_with(vol)
        self.assertEqual('error', vol.status)
        self.assertEqual(10, vol.size)

    def test_clone(self):
        vol = objects.Volume(self.backend_name, status='available', size=10,
                             extra_specs={'e': 'v'}, qos_specs={'q': 'qv'})
        mock_clone = self.backend.driver.create_cloned_volume
        mock_clone.return_value = None

        res = vol.clone(size=11)

        mock_clone.assert_called_once_with(res._ovo, vol._ovo)
        self.persistence.set_volume.assert_called_once_with(res)
        self.assertEqual('available', res.status)
        self.assertEqual(11, res.size)
        self.assertEqual(vol.id, vol.volume_type_id)
        self.assertNotEqual(vol.id, res.id)
        self.assertEqual(res.id, res.volume_type_id)
        self.assertEqual(vol.volume_type.extra_specs,
                         res.volume_type.extra_specs)
        self.assertEqual(vol.volume_type.qos_specs.specs,
                         res.volume_type.qos_specs.specs)

    def test_clone_error(self):
        vol = objects.Volume(self.backend_name, status='available', size=10)

        mock_clone = self.backend.driver.create_cloned_volume
        mock_clone.side_effect = exception.NotFound

        with self.assertRaises(exception.NotFound) as assert_context:
            vol.clone(size=11)

        # Cloning volume is still in flight
        self.assertEqual(1, len(self.backend._volumes_inflight))
        new_vol = list(self.backend._volumes_inflight.values())[0]
        self.assertEqual(new_vol, assert_context.exception.resource)
        mock_clone.assert_called_once_with(new_vol, vol._ovo)

        self.persistence.set_volume.assert_called_once_with(new_vol)
        self.assertEqual('error', new_vol.status)
        self.assertEqual(11, new_vol.size)

    def test_create_snapshot(self):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        mock_create = self.backend.driver.create_snapshot
        mock_create.return_value = None

        snap = vol.create_snapshot()

        self.assertEqual([snap], vol.snapshots)
        self.assertEqual([snap._ovo], vol._ovo.snapshots.objects)
        mock_create.assert_called_once_with(snap._ovo)
        self.assertEqual('available', snap.status)
        self.assertEqual(10, snap.volume_size)
        self.persistence.set_snapshot.assert_called_once_with(snap)

    def test_create_snapshot_error(self):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        mock_create = self.backend.driver.create_snapshot
        mock_create.side_effect = exception.NotFound

        self.assertRaises(exception.NotFound, vol.create_snapshot)

        self.assertEqual(1, len(vol.snapshots))
        snap = vol.snapshots[0]
        self.persistence.set_snapshot.assert_called_once_with(snap)
        self.assertEqual('error', snap.status)
        mock_create.assert_called_once_with(snap._ovo)

    @mock.patch('os_brick.initiator.connector.get_connector_properties')
    @mock.patch('cinderlib.objects.Volume.connect')
    def test_attach(self, mock_connect, mock_conn_props):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        res = vol.attach()

        mock_conn_props.assert_called_once_with(
            self.backend.root_helper,
            mock.ANY,
            self.backend.configuration.use_multipath_for_image_xfer,
            self.backend.configuration.enforce_multipath_for_image_xfer)

        mock_connect.assert_called_once_with(mock_conn_props.return_value)
        mock_connect.return_value.attach.assert_called_once_with()
        self.assertEqual(mock_connect.return_value, res)

    @mock.patch('os_brick.initiator.connector.get_connector_properties')
    @mock.patch('cinderlib.objects.Volume.connect')
    def test_attach_error_connect(self, mock_connect, mock_conn_props):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        mock_connect.side_effect = exception.NotFound

        self.assertRaises(exception.NotFound, vol.attach)

        mock_conn_props.assert_called_once_with(
            self.backend.root_helper,
            mock.ANY,
            self.backend.configuration.use_multipath_for_image_xfer,
            self.backend.configuration.enforce_multipath_for_image_xfer)

        mock_connect.assert_called_once_with(mock_conn_props.return_value)
        mock_connect.return_value.attach.assert_not_called()

    @mock.patch('cinderlib.objects.Volume.disconnect')
    @mock.patch('os_brick.initiator.connector.get_connector_properties')
    @mock.patch('cinderlib.objects.Volume.connect')
    def test_attach_error_attach(self, mock_connect, mock_conn_props,
                                 mock_disconnect):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        mock_attach = mock_connect.return_value.attach
        mock_attach.side_effect = exception.NotFound

        self.assertRaises(exception.NotFound, vol.attach)

        mock_conn_props.assert_called_once_with(
            self.backend.root_helper,
            mock.ANY,
            self.backend.configuration.use_multipath_for_image_xfer,
            self.backend.configuration.enforce_multipath_for_image_xfer)

        mock_connect.assert_called_once_with(mock_conn_props.return_value)
        mock_disconnect.assert_called_once_with(mock_connect.return_value)

    def test_detach_not_local(self):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        self.assertRaises(exception.NotLocal, vol.detach)

    def test_detach(self):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        mock_conn = mock.Mock()
        vol.local_attach = mock_conn

        vol.detach(mock.sentinel.force, mock.sentinel.ignore_errors)
        mock_conn.detach.assert_called_once_with(mock.sentinel.force,
                                                 mock.sentinel.ignore_errors,
                                                 mock.ANY)
        mock_conn.disconnect.assert_called_once_with(mock.sentinel.force)

    def test_detach_error_detach(self):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        mock_conn = mock.Mock()
        mock_conn.detach.side_effect = exception.NotFound
        vol.local_attach = mock_conn

        self.assertRaises(exception.NotFound,
                          vol.detach,
                          False, mock.sentinel.ignore_errors)

        mock_conn.detach.assert_called_once_with(False,
                                                 mock.sentinel.ignore_errors,
                                                 mock.ANY)
        mock_conn.disconnect.assert_not_called()

    def test_detach_error_disconnect(self):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        mock_conn = mock.Mock()
        mock_conn.disconnect.side_effect = exception.NotFound
        vol.local_attach = mock_conn

        self.assertRaises(objects.brick_exception.ExceptionChainer,
                          vol.detach,
                          mock.sentinel.force, False)

        mock_conn.detach.assert_called_once_with(mock.sentinel.force,
                                                 False,
                                                 mock.ANY)
        mock_conn.disconnect.assert_called_once_with(mock.sentinel.force)

    @mock.patch('cinderlib.objects.Connection.connect')
    def test_connect(self, mock_connect):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        mock_connect.return_value._ovo = objects.cinder_objs.VolumeAttachment()

        mock_export = self.backend.driver.create_export
        mock_export.return_value = None

        res = vol.connect(mock.sentinel.conn_dict)

        mock_connect.assert_called_once_with(vol, mock.sentinel.conn_dict)
        self.assertEqual([res], vol.connections)
        self.assertEqual([res._ovo], vol._ovo.volume_attachment.objects)
        self.assertEqual('in-use', vol.status)
        self.persistence.set_volume.assert_called_once_with(vol)

    @mock.patch('cinderlib.objects.Volume._remove_export')
    @mock.patch('cinderlib.objects.Connection.connect')
    def test_connect_error(self, mock_connect, mock_remove_export):
        vol = objects.Volume(self.backend_name, status='available', size=10)

        mock_export = self.backend.driver.create_export
        mock_export.return_value = None
        mock_connect.side_effect = exception.NotFound

        self.assertRaises(exception.NotFound,
                          vol.connect, mock.sentinel.conn_dict)

        mock_connect.assert_called_once_with(vol, mock.sentinel.conn_dict)
        self.assertEqual('available', vol.status)
        self.persistence.set_volume.assert_not_called()
        mock_remove_export.assert_called_once_with()

    @mock.patch('cinderlib.objects.Volume._disconnect')
    def test_disconnect(self, mock_disconnect):
        vol = objects.Volume(self.backend_name, status='available', size=10)
        mock_conn = mock.Mock()
        vol.disconnect(mock_conn, mock.sentinel.force)
        mock_conn._disconnect.assert_called_once_with(mock.sentinel.force)
        mock_disconnect.assert_called_once_with(mock_conn)

    @mock.patch('cinderlib.objects.Volume._remove_export')
    def test__disconnect(self, mock_remove_export):
        vol = objects.Volume(self.backend_name, status='in-use', size=10)

        vol._disconnect(mock.sentinel.connection)

        mock_remove_export.assert_called_once_with()
        self.assertEqual('available', vol.status)
        self.persistence.set_volume.assert_called_once_with(vol)

    def test__remove_export(self):
        vol = objects.Volume(self.backend_name, status='in-use', size=10)

        vol._remove_export()

        self.backend.driver.remove_export.assert_called_once_with(vol._context,
                                                                  vol._ovo)

    @mock.patch('cinderlib.objects.Volume._remove_export')
    def test_cleanup(self, mock_remove_export):
        vol = objects.Volume(self.backend_name, status='in-use', size=10)
        connections = [mock.Mock(), mock.Mock()]
        vol._connections = connections

        vol.cleanup()

        mock_remove_export.assert_called_once_with()
        for c in connections:
            c.detach.asssert_called_once_with()
