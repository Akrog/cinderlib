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

import cinderlib
from cinderlib.persistence import base


def get_mock_persistence():
    return mock.MagicMock(spec=base.PersistenceDriverBase)


class FakeBackend(cinderlib.Backend):
    def __init__(self, *args, **kwargs):
        driver_name = kwargs.get('volume_backend_name', 'fake')
        cinderlib.Backend.backends[driver_name] = self
        self._driver_cfg = {'volume_backend_name': driver_name}
        self.driver = mock.Mock()
        self.driver.persistence = cinderlib.Backend.persistence
        self._pool_names = (driver_name,)
        self._volumes = []
