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

"""Parent client for calling the Google Cloud Bigtable API.

This is the base from which all interactions with the API occur.

In the hierarchy of API concepts
* a client owns a cluster
* a cluster owns a table
* a table owns data
"""


import os
import six
import socket

try:
    from google.appengine.api import app_identity
except ImportError:
    app_identity = None

from gcloud_bigtable._generated import (
    bigtable_cluster_service_messages_pb2 as messages_pb2)
from gcloud_bigtable._generated import bigtable_cluster_service_pb2
from gcloud_bigtable.cluster_standalone import Cluster
from gcloud_bigtable.connection import TIMEOUT_SECONDS
from gcloud_bigtable.connection import make_stub


ADMIN_SCOPE = 'https://www.googleapis.com/auth/cloud-bigtable.admin'
"""Scope for interacting with the Cluster Admin and Table Admin APIs."""
DATA_SCOPE = 'https://www.googleapis.com/auth/cloud-bigtable.data'
"""Scope for reading and writing table data."""
READ_ONLY_SCOPE = ('https://www.googleapis.com/auth/'
                   'cloud-bigtable.data.readonly')
"""Scope for reading table data."""

PROJECT_ENV_VAR = 'GCLOUD_PROJECT'
"""Environment variable used to provide an implicit project ID."""
CLUSTER_ADMIN_HOST = 'bigtableclusteradmin.googleapis.com'
"""Cluster Admin API request host."""
CLUSTER_ADMIN_PORT = 443
"""Cluster Admin API request port."""

CLUSTER_STUB_FACTORY = (bigtable_cluster_service_pb2.
                        early_adopter_create_BigtableClusterService_stub)


def _project_id_from_environment():
    """Attempts to get the project ID from an environment variable.

    :rtype: string or :class:`NoneType`
    :returns: The project ID provided or ``None``
    """
    return os.getenv(PROJECT_ENV_VAR)


def _project_id_from_app_engine():
    """Gets the App Engine application ID if it can be inferred.

    :rtype: string or ``NoneType``
    :returns: App Engine application ID if running in App Engine,
              else ``None``.
    """
    if app_identity is None:
        return None

    return app_identity.get_application_id()


def _project_id_from_compute_engine():
    """Gets the Compute Engine project ID if it can be inferred.

    Uses 169.254.169.254 for the metadata server to avoid request
    latency from DNS lookup.

    See https://cloud.google.com/compute/docs/metadata#metadataserver
    for information about this IP address. (This IP is also used for
    Amazon EC2 instances, so the metadata flavor is crucial.)

    See https://github.com/google/oauth2client/issues/93 for context about
    DNS latency.

    :rtype: string or ``NoneType``
    :returns: Compute Engine project ID if the metadata service is available,
              else ``None``.
    """
    host = '169.254.169.254'
    uri_path = '/computeMetadata/v1/project/project-id'
    headers = {'Metadata-Flavor': 'Google'}
    connection = six.moves.http_client.HTTPConnection(host, timeout=0.1)

    try:
        connection.request('GET', uri_path, headers=headers)
        response = connection.getresponse()
        if response.status == 200:
            return response.read()
    except socket.error:  # socket.timeout or socket.error(64, 'Host is down')
        pass
    finally:
        connection.close()


def _determine_project_id(project_id):
    """Determine the project ID from the input or environment.

    When checking the environment, the following precedence is observed:

    * GCLOUD_PROJECT environment variable
    * Google App Engine application ID
    * Google Compute Engine project ID (from metadata server)

    :type project_id: string or :class:`NoneType`
    :param project_id: The ID of the project which owns the clusters, tables
                       and data. If not provided, will attempt to
                       determine from the environment.

    :rtype: string
    :returns: The project ID provided or inferred from the environment.
    :raises: :class:`EnvironmentError` if the project ID was not
             passed in and can't be inferred from the environment.
    """
    if project_id is None:
        project_id = _project_id_from_environment()

    if project_id is None:
        project_id = _project_id_from_app_engine()

    if project_id is None:
        project_id = _project_id_from_compute_engine()

    if project_id is None:
        raise EnvironmentError('Project ID was not provided and could not '
                               'be determined from environment.')

    return project_id


class Client(object):
    """Client for interacting with Google Cloud Bigtable API.

    :type credentials: :class:`oauth2client.client.OAuth2Credentials` or
                       :class:`NoneType`
    :param credentials: The OAuth2 Credentials to use for this cluster.

    :type project_id: string
    :param project_id: The ID of the project which owns the clusters, tables
                       and data. If not provided, will attempt to
                       determine from the environment.

    :type read_only: boolean
    :param read_only: Boolean indicating if the data scope should be
                      for reading only (or for writing as well).

    :type admin: boolean
    :param admin: Boolean indicating if the client will be used to interact
                  with the Cluster Admin or Table Admin APIs. This requires
                  the ``ADMIN_SCOPE``.

    :raises: :class:`ValueError` if both ``read_only`` and
             ``admin`` are ``True``
    """

    def __init__(self, credentials, project_id=None,
                 read_only=False, admin=False):
        if read_only and admin:
            raise ValueError('A read-only client cannot also perform'
                             'administrative actions.')

        scopes = []
        if read_only:
            scopes.append(READ_ONLY_SCOPE)
        else:
            scopes.append(DATA_SCOPE)

        if admin:
            scopes.append(ADMIN_SCOPE)

        self._credentials = credentials.create_scoped(scopes)
        self._project_id = _determine_project_id(project_id)

    @property
    def credentials(self):
        """Getter for client's credentials.

        :rtype: :class:`oauth2client.client.OAuth2Credentials`
        :returns: The credentials stored on the client.
        """
        return self._credentials

    @property
    def project_id(self):
        """Getter for client's project ID.

        :rtype: string
        :returns: The project ID stored on the client.
        """
        return self._project_id

    @property
    def project_name(self):
        """Project name to be used with Cluster Admin API.

        .. note::
          This property will not change if ``project_id`` does not, but the
          return value is not cached.

        The project name is of the form "projects/{project_id}".

        :rtype: string
        :returns: The project name to be used with the Cloud Bigtable Admin
                  API RPC service.
        """
        return 'projects/' + self._project_id

    def list_zones(self, timeout_seconds=TIMEOUT_SECONDS):
        """Lists zones associated with project.

        :type timeout_seconds: integer
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to ``TIMEOUT_SECONDS``.

        :rtype: list of strings
        :returns: The names of the zones
        """
        request_pb = messages_pb2.ListZonesRequest(name=self.project_name)
        stub = make_stub(self._credentials, CLUSTER_STUB_FACTORY,
                         CLUSTER_ADMIN_HOST, CLUSTER_ADMIN_PORT)
        with stub:
            response = stub.ListZones.async(request_pb, timeout_seconds)
            # We expect a `messages_pb2.ListZonesResponse`
            list_zones_response = response.result()

        return [zone.display_name for zone in list_zones_response.zones]

    def list_clusters(self, timeout_seconds=TIMEOUT_SECONDS):
        """Lists clusters owned by the project.

        :type timeout_seconds: integer
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to
                                ``TIMEOUT_SECONDS``.

        :rtype: tuple
        :returns: A pair of results, the first is a list of
                  :class:`.cluster_standalone.Cluster` s returned and the
                  second is a list of strings (the failed zones in the
                  request).
        """
        request_pb = messages_pb2.ListClustersRequest(name=self.project_name)
        stub = make_stub(self._credentials, CLUSTER_STUB_FACTORY,
                         CLUSTER_ADMIN_HOST, CLUSTER_ADMIN_PORT)
        with stub:
            response = stub.ListClusters.async(request_pb, timeout_seconds)
            # We expect a `messages_pb2.ListClustersResponse`
            list_clusters_response = response.result()

        failed_zones = [zone.display_name
                        for zone in list_clusters_response.failed_zones]
        clusters = [Cluster.from_pb(cluster_pb, self)
                    for cluster_pb in list_clusters_response.clusters]
        return clusters, failed_zones