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

from cinder import exception


NotFound = exception.NotFound
VolumeNotFound = exception.VolumeNotFound
SnapshotNotFound = exception.SnapshotNotFound
ConnectionNotFound = exception.VolumeAttachmentNotFound
InvalidVolume = exception.InvalidVolume


class InvalidPersistence(Exception):
    __msg = 'Invalid persistence storage: %s.'

    def __init__(self, name):
        super(InvalidPersistence, self).__init__(self.__msg % name)


class NotLocal(Exception):
    __msg = "Volume %s doesn't seem to be attached locally."

    def __init__(self, name):
        super(NotLocal, self).__init__(self.__msg % name)
