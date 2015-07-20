# Copyright 2015 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function

import os
import unittest2

from oauth2client.client import GoogleCredentials

from gcloud_bigtable._generated import (
    bigtable_cluster_service_messages_pb2 as messages)
from gcloud_bigtable.cluster_connection import ClusterConnection


PROJECT_ID = os.getenv('GCLOUD_TESTS_PROJECT_ID')


class TestClusterAdminAPI(unittest2.TestCase):

    def test_list_zones_as_user(self):
        credentials = GoogleCredentials.get_application_default()
        connection = ClusterConnection(credentials)
        result_pb = connection.list_zones(PROJECT_ID)
        self.assertTrue(isinstance(result_pb, messages.ListZonesResponse))

        self.assertEqual(len(result_pb.zones), 4)
        all_zones = sorted(result_pb.zones, key=lambda zone: zone.name)
        zone1, zone2, zone3, zone4 = all_zones

        OK_STATUS = 1
        self.assertEqual(zone1.name,
                         'projects/%s/zones/asia-east1-b' % (PROJECT_ID,))
        self.assertEqual(zone1.display_name, 'asia-east1-b')
        self.assertEqual(zone1.status, OK_STATUS)

        self.assertEqual(zone2.name,
                         'projects/%s/zones/europe-west1-c' % (PROJECT_ID,))
        self.assertEqual(zone2.display_name, 'europe-west1-c')
        self.assertEqual(zone2.status, OK_STATUS)

        self.assertEqual(zone3.name,
                         'projects/%s/zones/us-central1-b' % (PROJECT_ID,))
        self.assertEqual(zone3.display_name, 'us-central1-b')
        self.assertEqual(zone3.status, OK_STATUS)

        self.assertEqual(zone4.name,
                         'projects/%s/zones/us-central1-c' % (PROJECT_ID,))
        self.assertEqual(zone4.display_name, 'us-central1-c')
        self.assertEqual(zone4.status, OK_STATUS)