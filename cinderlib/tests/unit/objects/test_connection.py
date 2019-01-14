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

import ddt
import mock

from cinderlib import exception
from cinderlib import objects
from cinderlib.tests.unit import base


@ddt.ddt
class TestConnection(base.BaseTest):

    def setUp(self):
        self.original_is_multipathed = objects.Connection._is_multipathed_conn
        self.mock_is_mp = self.patch(
            'cinderlib.objects.Connection._is_multipathed_conn')
        self.mock_default = self.patch(
            'os_brick.initiator.DEVICE_SCAN_ATTEMPTS_DEFAULT')
        super(TestConnection, self).setUp()

        self.vol = objects.Volume(self.backend_name, size=10)
        self.kwargs = {'k1': 'v1', 'k2': 'v2'}
        self.conn = objects.Connection(self.backend, volume=self.vol,
                                       **self.kwargs)
        self.conn._ovo.connection_info = {
            'connector': {'multipath': mock.sentinel.mp_ovo_connector}}

    def test_init(self):
        self.mock_is_mp.assert_called_once_with(self.kwargs)
        self.assertEqual(self.conn.use_multipath, self.mock_is_mp.return_value)
        self.assertEqual(self.conn.scan_attempts, self.mock_default)
        self.assertIsNone(self.conn._connector)
        self.assertEqual(self.vol, self.conn._volume)
        self.assertEqual(self.vol._ovo, self.conn._ovo.volume)
        self.assertEqual(self.vol._ovo.id, self.conn._ovo.volume_id)

    def test__is_multipathed_conn_kwargs(self):
        res = self.original_is_multipathed(dict(
            use_multipath=mock.sentinel.mp_kwargs,
            connector={'multipath': mock.sentinel.mp_connector},
            __ovo=self.conn._ovo))
        self.assertEqual(mock.sentinel.mp_kwargs, res)

    def test__is_multipathed_conn_connector_kwarg(self):
        res = self.original_is_multipathed(dict(
            connector={'multipath': mock.sentinel.mp_connector},
            __ovo=self.conn._ovo))
        self.assertEqual(mock.sentinel.mp_connector, res)

    def test__is_multipathed_conn_connector_ovo(self):
        res = self.original_is_multipathed(dict(connector={},
                                                __ovo=self.conn._ovo))
        self.assertEqual(mock.sentinel.mp_ovo_connector, res)

    def test__is_multipathed_conn_connection_info_iscsi_true(self):
        res = self.original_is_multipathed(dict(
            connection_info={'conn': {'data': {'target_iqns': '',
                                               'target_portals': ''}}}))
        self.assertTrue(res)

    def test__is_multipathed_conn_connection_info_iscsi_false(self):
        res = self.original_is_multipathed(dict(
            connection_info={'conn': {'data': {'target_iqns': ''}}}))
        self.assertFalse(res)

    def test__is_multipathed_conn_connection_info_fc_true(self):
        res = self.original_is_multipathed(dict(
            connection_info={'conn': {'data': {'target_wwn': []}}}))
        self.assertTrue(res)

    def test__is_multipathed_conn_connection_info_fc_false(self):
        res = self.original_is_multipathed(dict(
            connection_info={'conn': {'data': {'target_wwn': ''}}}))
        self.assertFalse(res)

    def test_init_no_backend(self):
        self.assertRaises(TypeError, objects.Connection)

    def test_init_no_volume(self):
        self.mock_is_mp.reset_mock()
        conn = objects.Connection(self.backend, **self.kwargs)
        self.mock_is_mp.assert_called_once_with(self.kwargs)
        self.assertEqual(conn.use_multipath, self.mock_is_mp.return_value)
        self.assertEqual(conn.scan_attempts, self.mock_default)
        self.assertIsNone(conn._connector)

    def test_connect(self):
        connector = {'my_c': 'v'}
        conn = self.conn.connect(self.vol, connector)
        init_conn = self.backend.driver.initialize_connection
        init_conn.assert_called_once_with(self.vol, connector)
        self.assertIsInstance(conn, objects.Connection)
        self.assertEqual('attached', conn.status)
        self.assertEqual(init_conn.return_value, conn.connection_info['conn'])
        self.assertEqual(connector, conn.connector_info)
        self.persistence.set_connection.assert_called_once_with(conn)

    @mock.patch('cinderlib.objects.Volume._disconnect')
    @mock.patch('cinderlib.objects.Connection._disconnect')
    def test_disconnect(self, mock_disc, mock_vol_disc):
        self.conn.disconnect(force=mock.sentinel.force)
        mock_disc.assert_called_once_with(mock.sentinel.force)
        mock_vol_disc.assert_called_once_with(self.conn)

    def test__disconnect(self):
        conn_info = self.conn.connector_info
        self.conn._disconnect(mock.sentinel.force)
        self.backend.driver.terminate_connection.assert_called_once_with(
            self.vol._ovo, conn_info, force=mock.sentinel.force)
        self.assertEqual({}, self.conn.conn_info)
        self.assertEqual('detached', self.conn.status)
        self.persistence.delete_connection.assert_called_once_with(self.conn)

    @mock.patch('cinderlib.objects.Connection.conn_info', {'data': 'mydata'})
    @mock.patch('cinderlib.objects.Connection.path')
    @mock.patch('cinderlib.objects.Connection.device_attached')
    def test_attach(self, mock_attached, mock_path):
        with mock.patch('cinderlib.objects.Connection.connector') as mock_conn:
            self.conn.attach()
            mock_conn.connect_volume.assert_called_once_with('mydata')
            mock_attached.assert_called_once_with(
                mock_conn.connect_volume.return_value)
            mock_conn.check_valid_device.assert_called_once_with(mock_path)
            self.assertEqual(self.conn, self.vol.local_attach)

    @mock.patch('cinderlib.objects.Connection.conn_info', {'data': 'mydata'})
    @mock.patch('cinderlib.objects.Connection.device')
    def test_detach(self, mock_device):
        self.vol.local_attach = mock.Mock()
        with mock.patch('cinderlib.objects.Connection.connector') as mock_conn:
            self.conn.detach(mock.sentinel.force, mock.sentinel.ignore)
            mock_conn.disconnect_volume.assert_called_once_with(
                'mydata',
                mock_device,
                force=mock.sentinel.force,
                ignore_errors=mock.sentinel.ignore)
        self.assertIsNone(self.vol.local_attach)
        self.assertIsNone(self.conn.device)
        self.assertIsNone(self.conn._connector)
        self.persistence.set_connection.assert_called_once_with(self.conn)

    def test_get_by_id(self):
        self.persistence.get_connections.return_value = [mock.sentinel.conn]
        res = objects.Connection.get_by_id(mock.sentinel.conn_id)
        self.assertEqual(mock.sentinel.conn, res)
        self.persistence.get_connections.assert_called_once_with(
            connection_id=mock.sentinel.conn_id)

    def test_get_by_id_not_found(self):
        self.persistence.get_connections.return_value = None
        self.assertRaises(exception.ConnectionNotFound,
                          objects.Connection.get_by_id,
                          mock.sentinel.conn_id)
        self.persistence.get_connections.assert_called_once_with(
            connection_id=mock.sentinel.conn_id)

    def test_device_attached(self):
        self.conn.device_attached(mock.sentinel.device)
        self.assertEqual(mock.sentinel.device,
                         self.conn.connection_info['device'])
        self.persistence.set_connection.assert_called_once_with(self.conn)

    def test_conn_info_setter(self):
        self.conn.conn_info = mock.sentinel.conn_info
        self.assertEqual(mock.sentinel.conn_info,
                         self.conn._ovo.connection_info['conn'])

    def test_conn_info_setter_clear(self):
        self.conn.conn_info = mock.sentinel.conn_info
        self.conn.conn_info = {}
        self.assertIsNone(self.conn._ovo.connection_info)

    def test_conn_info_getter(self):
        self.conn.conn_info = mock.sentinel.conn_info
        self.assertEqual(mock.sentinel.conn_info, self.conn.conn_info)

    def test_conn_info_getter_none(self):
        self.conn.conn_info = None
        self.assertEqual({}, self.conn.conn_info)

    def test_protocol(self):
        self.conn.conn_info = {'driver_volume_type': mock.sentinel.iscsi}
        self.assertEqual(mock.sentinel.iscsi, self.conn.protocol)

    def test_connector_info_setter(self):
        self.conn.connector_info = mock.sentinel.connector
        self.assertEqual(mock.sentinel.connector,
                         self.conn._ovo.connection_info['connector'])
        self.assertIn('connection_info', self.conn._ovo._changed_fields)

    def test_connector_info_getter(self):
        self.conn.connector_info = mock.sentinel.connector
        self.assertEqual(mock.sentinel.connector, self.conn.connector_info)

    def test_connector_info_getter_empty(self):
        self.conn._ovo.connection_info = None
        self.assertIsNone(self.conn.connector_info)

    def test_device_setter(self):
        self.conn.device = mock.sentinel.device
        self.assertEqual(mock.sentinel.device,
                         self.conn._ovo.connection_info['device'])
        self.assertIn('connection_info', self.conn._ovo._changed_fields)

    def test_device_setter_none(self):
        self.conn.device = mock.sentinel.device
        self.conn.device = None
        self.assertNotIn('device', self.conn._ovo.connection_info)
        self.assertIn('connection_info', self.conn._ovo._changed_fields)

    def test_device_getter(self):
        self.conn.device = mock.sentinel.device
        self.assertEqual(mock.sentinel.device, self.conn.device)

    def test_path(self):
        self.conn.device = {'path': mock.sentinel.path}
        self.assertEqual(mock.sentinel.path, self.conn.path)

    @mock.patch('cinderlib.objects.Connection.conn_info')
    @mock.patch('cinderlib.objects.Connection.protocol')
    @mock.patch('os_brick.initiator.connector.InitiatorConnector.factory')
    def test_connector_getter(self, mock_connector, mock_proto, mock_info):
        res = self.conn.connector
        self.assertEqual(mock_connector.return_value, res)
        mock_connector.assert_called_once_with(
            mock_proto,
            self.backend.root_helper,
            use_multipath=self.mock_is_mp.return_value,
            device_scan_attempts=self.mock_default,
            conn=mock_info,
            do_local_attach=True)

        # Make sure we cache the value
        res = self.conn.connector
        self.assertEqual(1, mock_connector.call_count)

    @ddt.data(True, False)
    def test_attached_true(self, value):
        with mock.patch('cinderlib.objects.Connection.device', value):
            self.assertEqual(value, self.conn.attached)

    @ddt.data(True, False)
    def test_connected(self, value):
        with mock.patch('cinderlib.objects.Connection.conn_info', value):
            self.assertEqual(value, self.conn.connected)
