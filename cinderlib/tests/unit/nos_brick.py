# Copyright (c) 2019, Red Hat, Inc.
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

import errno

import mock

from cinderlib import nos_brick
from cinderlib.tests.unit import base


class TestRBDConnector(base.BaseTest):
    def setUp(self):
        self.connector = nos_brick.RBDConnector('sudo')
        self.connector.im_root = False
        self.containerized = False
        self.connector._setup_rbd_class = lambda *args: None

    @mock.patch.object(nos_brick.RBDConnector, '_execute')
    @mock.patch('os.makedirs')
    def test__ensure_dir(self, mkdir_mock, exec_mock):
        self.connector._ensure_dir(mock.sentinel.path)
        exec_mock.assert_called_once_with('mkdir', '-p', '-m0755',
                                          mock.sentinel.path, run_as_root=True)
        mkdir_mock.assert_not_called()

    @mock.patch.object(nos_brick.RBDConnector, '_execute')
    @mock.patch('os.makedirs')
    def test__ensure_dir_root(self, mkdir_mock, exec_mock):
        self.connector.im_root = True
        self.connector._ensure_dir(mock.sentinel.path)
        mkdir_mock.assert_called_once_with(mock.sentinel.path, 0o755)
        exec_mock.assert_not_called()

    @mock.patch.object(nos_brick.RBDConnector, '_execute')
    @mock.patch('os.makedirs', side_effect=OSError(errno.EEXIST, ''))
    def test__ensure_dir_root_exists(self, mkdir_mock, exec_mock):
        self.connector.im_root = True
        self.connector._ensure_dir(mock.sentinel.path)
        mkdir_mock.assert_called_once_with(mock.sentinel.path, 0o755)
        exec_mock.assert_not_called()

    @mock.patch.object(nos_brick.RBDConnector, '_execute')
    @mock.patch('os.makedirs', side_effect=OSError(errno.EPERM, ''))
    def test__ensure_dir_root_fails(self, mkdir_mock, exec_mock):
        self.connector.im_root = True
        with self.assertRaises(OSError) as exc:
            self.connector._ensure_dir(mock.sentinel.path)
        self.assertEqual(mkdir_mock.side_effect, exc.exception)
        mkdir_mock.assert_called_once_with(mock.sentinel.path, 0o755)
        exec_mock.assert_not_called()

    @mock.patch('os.path.realpath')
    @mock.patch.object(nos_brick.RBDConnector, '_execute')
    @mock.patch.object(nos_brick.RBDConnector, '_ensure_dir')
    @mock.patch('os.symlink')
    def test__ensure_link(self, link_mock, dir_mock, exec_mock, path_mock):
        source = '/dev/rbd0'
        link = '/dev/rbd/rbd/volume-xyz'
        self.connector._ensure_link(source, link)
        dir_mock.assert_called_once_with('/dev/rbd/rbd')
        exec_mock.assert_called_once_with('ln', '-s', '-f', source, link,
                                          run_as_root=True)
        link_mock.assert_not_called()
        path_mock.assert_not_called()

    @mock.patch('os.path.realpath')
    @mock.patch.object(nos_brick.RBDConnector, '_execute')
    @mock.patch.object(nos_brick.RBDConnector, '_ensure_dir')
    @mock.patch('os.symlink')
    def test__ensure_link_root(self, link_mock, dir_mock, exec_mock,
                               path_mock):
        self.connector.im_root = True
        source = '/dev/rbd0'
        link = '/dev/rbd/rbd/volume-xyz'
        self.connector._ensure_link(source, link)
        dir_mock.assert_called_once_with('/dev/rbd/rbd')
        exec_mock.assert_not_called()
        link_mock.assert_called_once_with(source, link)
        path_mock.assert_not_called()

    @mock.patch('os.path.realpath')
    @mock.patch.object(nos_brick.RBDConnector, '_execute')
    @mock.patch.object(nos_brick.RBDConnector, '_ensure_dir')
    @mock.patch('os.symlink', side_effect=OSError(errno.EEXIST, ''))
    def test__ensure_link_root_exists(self, link_mock, dir_mock, exec_mock,
                                      path_mock):
        self.connector.im_root = True
        source = '/dev/rbd0'
        path_mock.return_value = source
        link = '/dev/rbd/rbd/volume-xyz'
        self.connector._ensure_link(source, link)
        dir_mock.assert_called_once_with('/dev/rbd/rbd')
        exec_mock.assert_not_called()
        link_mock.assert_called_once_with(source, link)

    @mock.patch('os.path.realpath')
    @mock.patch.object(nos_brick.RBDConnector, '_execute')
    @mock.patch.object(nos_brick.RBDConnector, '_ensure_dir')
    @mock.patch('os.symlink', side_effect=OSError(errno.EPERM, ''))
    def test__ensure_link_root_fails(self, link_mock, dir_mock, exec_mock,
                                     path_mock):
        self.connector.im_root = True
        source = '/dev/rbd0'
        path_mock.return_value = source
        link = '/dev/rbd/rbd/volume-xyz'

        with self.assertRaises(OSError) as exc:
            self.connector._ensure_link(source, link)

        self.assertEqual(link_mock.side_effect, exc.exception)
        dir_mock.assert_called_once_with('/dev/rbd/rbd')
        exec_mock.assert_not_called()
        link_mock.assert_called_once_with(source, link)

    @mock.patch('os.remove')
    @mock.patch('os.path.realpath')
    @mock.patch.object(nos_brick.RBDConnector, '_execute')
    @mock.patch.object(nos_brick.RBDConnector, '_ensure_dir')
    @mock.patch('os.symlink', side_effect=[OSError(errno.EEXIST, ''), None])
    def test__ensure_link_root_replace(self, link_mock, dir_mock, exec_mock,
                                       path_mock, remove_mock):
        self.connector.im_root = True
        source = '/dev/rbd0'
        path_mock.return_value = '/dev/rbd1'
        link = '/dev/rbd/rbd/volume-xyz'
        self.connector._ensure_link(source, link)
        dir_mock.assert_called_once_with('/dev/rbd/rbd')
        exec_mock.assert_not_called()
        remove_mock.assert_called_once_with(link)
        self.assertListEqual(
            [mock.call(source, link), mock.call(source, link)],
            link_mock.mock_calls)
