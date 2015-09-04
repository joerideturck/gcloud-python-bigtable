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

"""Google Cloud Bigtable HappyBase connection module."""

# Constants reproduced here for compatibility, though values are
# all null.
COMPAT_MODES = None
THRIFT_TRANSPORTS = None
THRIFT_PROTOCOLS = None
DEFAULT_HOST = None
DEFAULT_PORT = None
DEFAULT_TRANSPORT = None
DEFAULT_COMPAT = None
DEFAULT_PROTOCOL = None


class Connection(object):
    """Connection to Cloud Bigtable backend.

    :type host: :data:`NoneType <types.NoneType>`
    :param host: Unused parameter. Provided for compatibility with HappyBase,
                 but irrelevant for Cloud Bigtable since it has a fixed host.

    :type port: :data:`NoneType <types.NoneType>`
    :param port: Unused parameter. Provided for compatibility with HappyBase,
                 but irrelevant for Cloud Bigtable since it has a fixed host.

    :type timeout: int
    :param timeout: (Optional) The socket timeout in milliseconds.

    :type autoconnect: bool
    :param autoconnect: Whether the connection should be :meth:`open`-ed
                        during construction.

    :type table_prefix: str
    :param table_prefix: (Optional) Prefix used to construct table names.

    :type table_prefix_separator: str
    :param table_prefix_separator: Separator used with ``table_prefix``.

    :type compat: :data:`NoneType <types.NoneType>`
    :param compat: Unused parameter. Provided for compatibility with
                   HappyBase, but irrelevant for Cloud Bigtable since there
                   is only one version.

    :type transport: :data:`NoneType <types.NoneType>`
    :param transport: Unused parameter. Provided for compatibility with
                      HappyBase, but irrelevant for Cloud Bigtable since the
                      transport is fixed.

    :type protocol: :data:`NoneType <types.NoneType>`
    :param protocol: Unused parameter. Provided for compatibility with
                     HappyBase, but irrelevant for Cloud Bigtable since the
                     protocol is fixed.

    :raises: :class:`ValueError <exceptions.ValueError>` if any of the unused
             parameters are specified with a value other than the defaults.
    """

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=None,
                 autoconnect=True, table_prefix=None,
                 table_prefix_separator='_', compat=DEFAULT_COMPAT,
                 transport=DEFAULT_TRANSPORT, protocol=DEFAULT_PROTOCOL):
        if host is not DEFAULT_HOST:
            raise ValueError('Host cannot be set for gcloud HappyBase module')
        if port is not DEFAULT_PORT:
            raise ValueError('Port cannot be set for gcloud HappyBase module')
        if compat is not DEFAULT_COMPAT:
            raise ValueError('Compat cannot be set for gcloud '
                             'HappyBase module')
        if transport is not DEFAULT_TRANSPORT:
            raise ValueError('Transport cannot be set for gcloud '
                             'HappyBase module')
        if protocol is not DEFAULT_PROTOCOL:
            raise ValueError('Protocol cannot be set for gcloud '
                             'HappyBase module')

        self.timeout = timeout
        self.table_prefix = table_prefix
        self.table_prefix_separator = table_prefix_separator

        if autoconnect:
            self.open()

    def open(self):
        """Open the underlying transport to Cloud Bigtable.

        :raises: :class:`NotImplementedError <exceptions.NotImplementedError>`
                 temporarily until the method is implemented.
        """
        raise NotImplementedError('Temporarily not implemented.')

    def close(self):
        """Close the underlying transport to Cloud Bigtable.

        :raises: :class:`NotImplementedError <exceptions.NotImplementedError>`
                 temporarily until the method is implemented.
        """
        raise NotImplementedError('Temporarily not implemented.')

    def table(self, name, use_prefix=True):
        """Table factory.

        :type name: str
        :param name: The name of the table to be created.

        :type use_prefix: bool
        :param use_prefix: Whether to use the table prefix (if any).

        :raises: :class:`NotImplementedError <exceptions.NotImplementedError>`
                 temporarily until the method is implemented.
        """
        raise NotImplementedError('Temporarily not implemented.')

    def tables(self):
        """Return a list of table names available to this connection.

        The connection is limited to a cluster in Cloud Bigtable.

        :raises: :class:`NotImplementedError <exceptions.NotImplementedError>`
                 temporarily until the method is implemented.
        """
        raise NotImplementedError('Temporarily not implemented.')

    def create_table(self, name, families):
        """Create a table.

        :type name: str
        :param name: The name of the table to be created.

        :type families: dict
        :param families: The name and options for each column family.

        :raises: :class:`NotImplementedError <exceptions.NotImplementedError>`
                 temporarily until the method is implemented.
        """
        raise NotImplementedError('Temporarily not implemented.')

    def delete_table(self, name, disable=False):
        """Delete the specified table.

        :type name: str
        :param name: The name of the table to be deleted.

        :type disable: bool
        :param disable: Whether to first disable the table if needed. This
                        is provided for compatibility with happybase, but is
                        not relevant for Cloud Bigtable since it has no concept
                        of enabled / disabled tables.

        :raises: :class:`NotImplementedError <exceptions.NotImplementedError>`
                 temporarily until the method is implemented.
        """
        raise NotImplementedError('Temporarily not implemented.')

    def enable_table(self, name):
        """Enable the specified table.

        Cloud Bigtable has no concept of enabled / disabled tables so this
        method does not work. It is provided simply for compatibility.

        :raises: :class:`NotImplementedError <exceptions.NotImplementedError>`
                 always
        """
        raise NotImplementedError('The Cloud Bigtable API has no concept of '
                                  'enabled or disabled tables.')

    def disable_table(self, name):
        """Disable the specified table.

        Cloud Bigtable has no concept of enabled / disabled tables so this
        method does not work. It is provided simply for compatibility.

        :raises: :class:`NotImplementedError <exceptions.NotImplementedError>`
                 always
        """
        raise NotImplementedError('The Cloud Bigtable API has no concept of '
                                  'enabled or disabled tables.')

    def is_table_enabled(self, name):
        """Return whether the specified table is enabled.

        Cloud Bigtable has no concept of enabled / disabled tables so this
        method does not work. It is provided simply for compatibility.

        :raises: :class:`NotImplementedError <exceptions.NotImplementedError>`
                 always
        """
        raise NotImplementedError('The Cloud Bigtable API has no concept of '
                                  'enabled or disabled tables.')

    def compact_table(self, name, major=False):
        """Compact the specified table.

        Cloud Bigtable does not support compacting a table, so this
        method does not work. It is provided simply for compatibility.

        :raises: :class:`NotImplementedError <exceptions.NotImplementedError>`
                 always
        """
        raise NotImplementedError('The Cloud Bigtable API does not support '
                                  'compacting a table.')