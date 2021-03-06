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

"""User friendly container for Google Cloud Bigtable Row."""


import six
import struct

from gcloud_bigtable._generated import bigtable_data_pb2 as data_pb2
from gcloud_bigtable._generated import (
    bigtable_service_messages_pb2 as messages_pb2)
from gcloud_bigtable._helpers import _parse_family_pb
from gcloud_bigtable._helpers import _timestamp_to_microseconds
from gcloud_bigtable._helpers import _to_bytes


_MAX_MUTATIONS = 100000
_PACK_I64 = struct.Struct('>q').pack


class Row(object):
    """Representation of a Google Cloud Bigtable Row.

    .. note::

        A :class:`Row` accumulates mutations locally via the :meth:`set_cell`,
        :meth:`delete`, :meth:`delete_cell` and :meth:`delete_cells` methods.
        To actually send these mutations to the Google Cloud Bigtable API, you
        must call :meth:`commit`. If a ``filter_`` is set on the :class:`Row`,
        the mutations must have an associated state: :data:`True` or
        :data:`False`. The mutations will be applied conditionally, based on
        whether the filter matches any cells in the :class:`Row` or not.

    :type row_key: bytes
    :param row_key: The key for the current row.

    :type table: :class:`Table <gcloud_bigtable.table.Table>`
    :param table: The table that owns the row.

    :type filter_: :class:`RowFilter`, :class:`RowFilterChain`,
                   :class:`RowFilterUnion` or :class:`ConditionalRowFilter`
    :param filter_: (Optional) Filter to be used for conditional mutations.
                    If a filter is set, then the :class:`Row` will accumulate
                    mutations for either a :data:`True` or :data:`False` state.
                    When :meth:`commit`-ed, the mutations for the :data:`True`
                    state will be applied if the filter matches any cells in
                    the row, otherwise the :data:`False` state will be.
    """

    ALL_COLUMNS = object()
    """Sentinel value used to indicate all columns in a column family."""

    def __init__(self, row_key, table, filter_=None):
        self._row_key = _to_bytes(row_key)
        self._table = table
        self._filter = filter_
        self._rule_pb_list = []
        if self._filter is None:
            self._pb_mutations = []
            self._true_pb_mutations = None
            self._false_pb_mutations = None
        else:
            self._pb_mutations = None
            self._true_pb_mutations = []
            self._false_pb_mutations = []

    @property
    def table(self):
        """Getter for row's table.

        :rtype: :class:`Table <gcloud_bigtable.table.Table>`
        :returns: The table stored on the row.
        """
        return self._table

    @property
    def row_key(self):
        """Getter for row's key.

        :rtype: bytes
        :returns: The key for the row.
        """
        return self._row_key

    @property
    def filter(self):
        """Getter for row's filter.

        :rtype: :class:`RowFilter`, :class:`RowFilterChain`,
                :class:`RowFilterUnion`, :class:`ConditionalRowFilter` or
                :data:`NoneType <types.NoneType>`
        :returns: The filter for the row.
        """
        return self._filter

    @property
    def client(self):
        """Getter for row's client.

        :rtype: :class:`.client.Client`
        :returns: The client that owns this row.
        """
        return self.table.client

    @property
    def timeout_seconds(self):
        """Getter for row's default timeout seconds.

        :rtype: int
        :returns: The timeout seconds default.
        """
        return self.table.timeout_seconds

    def _get_mutations(self, state=None):
        """Gets the list of mutations for a given state.

        If the state is :data`None` but there is a filter set, then we've
        reached an invalid state. Similarly if no filter is set but the
        state is not :data:`None`.

        :type state: bool
        :param state: (Optional) The state that the mutation should be
                      applied in. Unset if the mutation is not conditional,
                      otherwise :data:`True` or :data:`False`.

        :rtype: list
        :returns: The list to add new mutations to (for the current state).
        :raises: :class:`ValueError <exceptions.ValueError>`
        """
        if state is None:
            if self.filter is not None:
                raise ValueError('A filter is set on the current row, but no '
                                 'state given for the mutation')
            return self._pb_mutations
        else:
            if self.filter is None:
                raise ValueError('No filter was set on the current row, but a '
                                 'state was given for the mutation')
            if state:
                return self._true_pb_mutations
            else:
                return self._false_pb_mutations

    def set_cell(self, column_family_id, column, value, timestamp=None,
                 state=None):
        """Sets a value in this row.

        The cell is determined by the ``row_key`` of the :class:`Row` and the
        ``column``. The ``column`` must be in an existing
        :class:`.column_family.ColumnFamily` (as determined by
        ``column_family_id``).

        .. note::

            This method adds a mutation to the accumulated mutations on this
            :class:`Row`, but does not make an API request. To actually
            send an API request (with the mutations) to the Google Cloud
            Bigtable API, call :meth:`commit`.

        :type column_family_id: str
        :param column_family_id: The column family that contains the column.
                                 Must be of the form
                                 ``[_a-zA-Z0-9][-_.a-zA-Z0-9]*``.

        :type column: bytes
        :param column: The column within the column family where the cell
                       is located.

        :type value: bytes or :class:`int`
        :param value: The value to set in the cell. If an integer is used,
                      will be interpreted as a 64-bit big-endian signed
                      integer (8 bytes).

        :type timestamp: :class:`datetime.datetime`
        :param timestamp: (Optional) The timestamp of the operation.

        :type state: bool
        :param state: (Optional) The state that the mutation should be
                      applied in. Unset if the mutation is not conditional,
                      otherwise :data:`True` or :data:`False`.
        """
        column = _to_bytes(column)
        if isinstance(value, six.integer_types):
            value = _PACK_I64(value)
        value = _to_bytes(value)
        if timestamp is None:
            # Use -1 for current Bigtable server time.
            timestamp_micros = -1
        else:
            timestamp_micros = _timestamp_to_microseconds(timestamp)

        mutation_val = data_pb2.Mutation.SetCell(
            family_name=column_family_id,
            column_qualifier=column,
            timestamp_micros=timestamp_micros,
            value=value,
        )
        mutation_pb = data_pb2.Mutation(set_cell=mutation_val)
        self._get_mutations(state).append(mutation_pb)

    def append_cell_value(self, column_family_id, column, value):
        """Appends a value to an existing cell.

        .. note::

            This method adds a read-modify rule protobuf to the accumulated
            read-modify rules on this :class:`Row`, but does not make an API
            request. To actually send an API request (with the rules) to the
            Google Cloud Bigtable API, call :meth:`commit_modifications`.

        :type column_family_id: str
        :param column_family_id: The column family that contains the column.
                                 Must be of the form
                                 ``[_a-zA-Z0-9][-_.a-zA-Z0-9]*``.

        :type column: bytes
        :param column: The column within the column family where the cell
                       is located.

        :type value: bytes
        :param value: The value to append to the existing value in the cell. If
                      the targeted cell is unset, it will be treated as
                      containing the empty string.
        """
        column = _to_bytes(column)
        value = _to_bytes(value)
        rule_pb = data_pb2.ReadModifyWriteRule(family_name=column_family_id,
                                               column_qualifier=column,
                                               append_value=value)
        self._rule_pb_list.append(rule_pb)

    def increment_cell_value(self, column_family_id, column, int_value):
        """Increments a value in an existing cell.

        Assumes the value in the cell is stored as a 64 bit integer
        serialized to bytes.

        .. note::

            This method adds a read-modify rule protobuf to the accumulated
            read-modify rules on this :class:`Row`, but does not make an API
            request. To actually send an API request (with the rules) to the
            Google Cloud Bigtable API, call :meth:`commit_modifications`.

        :type column_family_id: str
        :param column_family_id: The column family that contains the column.
                                 Must be of the form
                                 ``[_a-zA-Z0-9][-_.a-zA-Z0-9]*``.

        :type column: bytes
        :param column: The column within the column family where the cell
                       is located.

        :type int_value: int
        :param int_value: The value to increment the existing value in the cell
                          by. If the targeted cell is unset, it will be treated
                          as containing a zero. Otherwise, the targeted cell
                          must contain an 8-byte value (interpreted as a 64-bit
                          big-endian signed integer), or the entire request
                          will fail.
        """
        column = _to_bytes(column)
        rule_pb = data_pb2.ReadModifyWriteRule(family_name=column_family_id,
                                               column_qualifier=column,
                                               increment_amount=int_value)
        self._rule_pb_list.append(rule_pb)

    def delete(self, state=None):
        """Deletes this row from the table.

        .. note::

            This method adds a mutation to the accumulated mutations on this
            :class:`Row`, but does not make an API request. To actually
            send an API request (with the mutations) to the Google Cloud
            Bigtable API, call :meth:`commit`.

        :type state: bool
        :param state: (Optional) The state that the mutation should be
                      applied in. Unset if the mutation is not conditional,
                      otherwise :data:`True` or :data:`False`.
        """
        mutation_val = data_pb2.Mutation.DeleteFromRow()
        mutation_pb = data_pb2.Mutation(delete_from_row=mutation_val)
        self._get_mutations(state).append(mutation_pb)

    def delete_cell(self, column_family_id, column, time_range=None,
                    state=None):
        """Deletes cell in this row.

        .. note::

            This method adds a mutation to the accumulated mutations on this
            :class:`Row`, but does not make an API request. To actually
            send an API request (with the mutations) to the Google Cloud
            Bigtable API, call :meth:`commit`.

        :type column_family_id: str
        :param column_family_id: The column family that contains the column
                                 or columns with cells being deleted. Must be
                                 of the form ``[_a-zA-Z0-9][-_.a-zA-Z0-9]*``.

        :type column: bytes
        :param column: The column within the column family that will have a
                       cell deleted.

        :type time_range: :class:`TimestampRange`
        :param time_range: (Optional) The range of time within which cells
                           should be deleted.

        :type state: bool
        :param state: (Optional) The state that the mutation should be
                      applied in. Unset if the mutation is not conditional,
                      otherwise :data:`True` or :data:`False`.
        """
        self.delete_cells(column_family_id, [column], time_range=time_range,
                          state=state)

    def delete_cells(self, column_family_id, columns, time_range=None,
                     state=None):
        """Deletes cells in this row.

        .. note::

            This method adds a mutation to the accumulated mutations on this
            :class:`Row`, but does not make an API request. To actually
            send an API request (with the mutations) to the Google Cloud
            Bigtable API, call :meth:`commit`.

        :type column_family_id: str
        :param column_family_id: The column family that contains the column
                                 or columns with cells being deleted. Must be
                                 of the form ``[_a-zA-Z0-9][-_.a-zA-Z0-9]*``.

        :type columns: :class:`list` of :class:`str` /
                       :func:`unicode <unicode>`, or :class:`object`
        :param columns: The columns within the column family that will have
                        cells deleted. If :attr:`Row.ALL_COLUMNS` is used then
                        the entire column family will be deleted from the row.

        :type time_range: :class:`TimestampRange`
        :param time_range: (Optional) The range of time within which cells
                           should be deleted.

        :type state: bool
        :param state: (Optional) The state that the mutation should be
                      applied in. Unset if the mutation is not conditional,
                      otherwise :data:`True` or :data:`False`.
        """
        mutations_list = self._get_mutations(state)
        if columns is self.ALL_COLUMNS:
            mutation_val = data_pb2.Mutation.DeleteFromFamily(
                family_name=column_family_id,
            )
            mutation_pb = data_pb2.Mutation(delete_from_family=mutation_val)
            mutations_list.append(mutation_pb)
        else:
            delete_kwargs = {}
            if time_range is not None:
                delete_kwargs['time_range'] = time_range.to_pb()

            to_append = []
            for column in columns:
                column = _to_bytes(column)
                # time_range will never change if present, but the rest of
                # delete_kwargs will
                delete_kwargs.update(
                    family_name=column_family_id,
                    column_qualifier=column,
                )
                mutation_val = data_pb2.Mutation.DeleteFromColumn(
                    **delete_kwargs)
                mutation_pb = data_pb2.Mutation(
                    delete_from_column=mutation_val)
                to_append.append(mutation_pb)

            # We don't add the mutations until all columns have been
            # processed without error.
            mutations_list.extend(to_append)

    def _commit_mutate(self, timeout_seconds=None, async=True):
        """Makes a ``MutateRow`` API request.

        Assumes no filter is set on the :class:`Row` and is meant to be called
        by :meth:`commit`.

        :type timeout_seconds: int
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to value set on row.

        :type async: bytes
        :param async: Boolean indicating if the GRPC call should be done asynchronous

        :raises: :class:`ValueError <exceptions.ValueError>` if the number of
                 mutations exceeds the ``_MAX_MUTATIONS``.
        """
        mutations_list = self._get_mutations(None)
        num_mutations = len(mutations_list)
        if num_mutations == 0:
            return
        if num_mutations > _MAX_MUTATIONS:
            raise ValueError('%d total mutations exceed the maximum allowable '
                             '%d.' % (num_mutations, _MAX_MUTATIONS))
        request_pb = messages_pb2.MutateRowRequest(
            table_name=self.table.name,
            row_key=self.row_key,
            mutations=mutations_list,
        )
        timeout_seconds = timeout_seconds or self.timeout_seconds
        # We expect a `._generated.empty_pb2.Empty`.
        if async:
            self.client.data_stub.MutateRow.async(request_pb, timeout_seconds).result()
        else:
            self.client.data_stub.MutateRow(request_pb, timeout_seconds)

    def _commit_check_and_mutate(self, timeout_seconds=None, async=True):
        """Makes a ``CheckAndMutateRow`` API request.

        Assumes a filter is set on the :class:`Row` and is meant to be called
        by :meth:`commit`.

        :type timeout_seconds: int
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to value set on row.

        :type async: bool
        :param async: Boolean indicating if the GRPC call should be done asynchronously

        :rtype: bool
        :returns: Flag indicating if the filter was matched (which also
                  indicates which set of mutations were applied by the server).
        :raises: :class:`ValueError <exceptions.ValueError>` if the number of
                 mutations exceeds the ``_MAX_MUTATIONS``.
        """
        true_mutations = self._get_mutations(True)
        false_mutations = self._get_mutations(False)
        num_true_mutations = len(true_mutations)
        num_false_mutations = len(false_mutations)
        if num_true_mutations == 0 and num_false_mutations == 0:
            return
        if (num_true_mutations > _MAX_MUTATIONS or
                num_false_mutations > _MAX_MUTATIONS):
            raise ValueError(
                'Exceed the maximum allowable mutations (%d). Had %s true '
                'mutations and %d false mutations.' % (
                    _MAX_MUTATIONS, num_true_mutations, num_false_mutations))

        request_pb = messages_pb2.CheckAndMutateRowRequest(
            table_name=self.table.name,
            row_key=self.row_key,
            predicate_filter=self.filter.to_pb(),
            true_mutations=true_mutations,
            false_mutations=false_mutations,
        )
        timeout_seconds = timeout_seconds or self.timeout_seconds
        # We expect a `.messages_pb2.CheckAndMutateRowResponse`
        if async:
            response = self.client.data_stub.CheckAndMutateRow.async(request_pb, timeout_seconds)
            check_and_mutate_row_response = response.result()
        else:
            check_and_mutate_row_response = self.client.data_stub.CheckAndMutateRow(request_pb, timeout_seconds)

        return check_and_mutate_row_response.predicate_matched

    def clear_mutations(self):
        """Removes all currently accumulated mutations on the current row."""
        if self.filter is None:
            self._pb_mutations[:] = []
        else:
            self._true_pb_mutations[:] = []
            self._false_pb_mutations[:] = []

    def commit(self, timeout_seconds=None, async=True):
        """Makes a ``MutateRow`` or ``CheckAndMutateRow`` API request.

        If no mutations have been created in the row, no request is made.

        Mutations are applied atomically and in order, meaning that earlier
        mutations can be masked / negated by later ones. Cells already present
        in the row are left unchanged unless explicitly changed by a mutation.

        After committing the accumulated mutations, resets the local
        mutations to an empty list.

        In the case that a filter is set on the :class:`Row`, the mutations
        will be applied conditionally, based on whether the filter matches
        any cells in the :class:`Row` or not. (Each method which adds a
        mutation has a ``state`` parameter for this purpose.)

        :type timeout_seconds: int
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to value set on row.

        :type async: bool
        :param async: Boolean indicating if the GRPC call should be done asynchronously

        :rtype: :class:`bool` or :data:`NoneType <types.NoneType>`
        :returns: :data:`None` if there is no filter, otherwise a flag
                  indicating if the filter was matched (which also
                  indicates which set of mutations were applied by the server).
        :raises: :class:`ValueError <exceptions.ValueError>` if the number of
                 mutations exceeds the ``_MAX_MUTATIONS``.
        """
        if self.filter is None:
            result = self._commit_mutate(timeout_seconds=timeout_seconds, async=async)
        else:
            result = self._commit_check_and_mutate(
                timeout_seconds=timeout_seconds, async=async)

        # Reset mutations after commit-ing request.
        self.clear_mutations()

        return result

    def clear_modification_rules(self):
        """Removes all currently accumulated modifications on current row."""
        self._rule_pb_list[:] = []

    def commit_modifications(self, timeout_seconds=None, async=True):
        """Makes a ``ReadModifyWriteRow`` API request.

        This commits modifications made by :meth:`append_cell_value` and
        :meth:`increment_cell_value`. If no modifications were made, makes
        no API request and just returns ``{}``.

        Modifies a row atomically, reading the latest existing timestamp/value
        from the specified columns and writing a new value by appending /
        incrementing. The new cell created uses either the current server time
        or the highest timestamp of a cell in that column (if it exceeds the
        server time).

        :type timeout_seconds: int
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to value set on row.

        :type async: bool
        :param async: Boolean indicating if the GRPC call should be done asynchronously

        :rtype: dict
        :returns: The new contents of all modified cells. Returned as a
                  dictionary of column families, each of which holds a
                  dictionary of columns. Each column contains a list of cells
                  modified. Each cell is represented with a two-tuple with the
                  value (in bytes) and the timestamp for the cell. For example:

                  .. code:: python

                      {
                          u'col-fam-id': {
                              b'col-name1': [
                                  (b'cell-val', datetime.datetime(...)),
                                  (b'cell-val-newer', datetime.datetime(...)),
                              ],
                              b'col-name2': [
                                  (b'altcol-cell-val', datetime.datetime(...)),
                              ],
                          },
                          u'col-fam-id2': {
                              b'col-name3-but-other-fam': [
                                  (b'foo', datetime.datetime(...)),
                              ],
                          },
                      }
        """
        if len(self._rule_pb_list) == 0:
            return {}
        request_pb = messages_pb2.ReadModifyWriteRowRequest(
            table_name=self.table.name,
            row_key=self.row_key,
            rules=self._rule_pb_list,
        )
        timeout_seconds = timeout_seconds or self.timeout_seconds

        # We expect a `.data_pb2.Row`
        if async:
            response = self.client.data_stub.ReadModifyWriteRow.async(request_pb, timeout_seconds)
            row_response = response.result()
        else:
            row_response = self.client.data_stub.ReadModifyWriteRow(request_pb, timeout_seconds)

        # Reset modifications after commit-ing request.
        self.clear_modification_rules()

        # NOTE: We expect row_response.key == self.row_key but don't check.
        return _parse_rmw_row_response(row_response)


# NOTE: For developers, this class may seem to be a bit verbose, i.e.
#       a list of property names and **kwargs may do the trick better
#       than actually listing every single argument. However, for the sake
#       of users and documentation, listing every single argument is more
#       useful.
class RowFilter(object):
    """Basic filter to apply to cells in a row.

    These values can be combined via :class:`RowFilterChain`,
    :class:`RowFilterUnion` and :class:`ConditionalRowFilter`.

    The regex filters must be valid RE2 patterns. See Google's
    `RE2 reference`_ for the accepted syntax.

    .. _RE2 reference: https://github.com/google/re2/wiki/Syntax

    .. note::

        At most one of the keyword arguments can be specified at once.

    .. note::

        For :class:`bytes` regex filters (``row_key``, ``column_qualifier`` and
        ``value``), special care need be used with the expression used. Since
        each of these properties can contain arbitrary bytes, the ``\\C``
        escape sequence must be used if a true wildcard is desired. The ``.``
        character will not match the new line character ``\\n``, which may be
        present in a binary value.

    :type row_key_regex_filter: bytes
    :param row_key_regex_filter: A regular expression (RE2) to match cells from
                                 rows with row keys that satisfy this regex.
                                 For a ``CheckAndMutateRowRequest``, this
                                 filter is unnecessary since the row key is
                                 already specified.

    :type family_name_regex_filter: str
    :param family_name_regex_filter: A regular expression (RE2) to match cells
                                     from columns in a given column family. For
                                     technical reasons, the regex must not
                                     contain the ``':'`` character, even if it
                                     isnot being uses as a literal.

    :type column_qualifier_regex_filter: bytes
    :param column_qualifier_regex_filter: A regular expression (RE2) to match
                                          cells from column that match this
                                          regex (irrespective of column
                                          family).

    :type value_regex_filter: bytes
    :param value_regex_filter: A regular expression (RE2) to match cells with
                               values that match this regex.

    :type column_range_filter: :class:`ColumnRange`
    :param column_range_filter: Range of columns to limit cells to.

    :type timestamp_range_filter: :class:`TimestampRange`
    :param timestamp_range_filter: Range of time that cells should match
                                   against.

    :type value_range_filter: :class:`CellValueRange`
    :param value_range_filter: Range of cell values to filter for.

    :type cells_per_row_offset_filter: int
    :param cells_per_row_offset_filter: Skips the first N cells of the row.

    :type cells_per_row_limit_filter: int
    :param cells_per_row_limit_filter: Matches only the first N cells of the
                                       row.

    :type cells_per_column_limit_filter: int
    :param cells_per_column_limit_filter: Matches only the most recent N cells
                                          within each column. This filters a
                                          (family name, column) pair, based on
                                          timestamps of each cell.

    :type row_sample_filter: float
    :param row_sample_filter: Non-deterministic filter. Matches all cells from
                              a row with probability p, and matches no cells
                              from the row with probability 1-p. (Here, the
                              probability p is ``row_sample_filter``.)

    :type strip_value_transformer: bool
    :param strip_value_transformer: If :data:`True`, replaces each cell's value
                                    with the empty string. As the name
                                    indicates, this is more useful as a
                                    transformer than a generic query / filter.

    :raises: :class:`TypeError <exceptions.TypeError>` if not exactly one
             value set in the constructor.
    """

    def __init__(self,
                 row_key_regex_filter=None,
                 family_name_regex_filter=None,
                 column_qualifier_regex_filter=None,
                 value_regex_filter=None,
                 column_range_filter=None,
                 timestamp_range_filter=None,
                 value_range_filter=None,
                 cells_per_row_offset_filter=None,
                 cells_per_row_limit_filter=None,
                 cells_per_column_limit_filter=None,
                 row_sample_filter=None,
                 strip_value_transformer=None):
        self.row_key_regex_filter = row_key_regex_filter
        self.family_name_regex_filter = family_name_regex_filter
        self.column_qualifier_regex_filter = column_qualifier_regex_filter
        self.value_regex_filter = value_regex_filter
        self.column_range_filter = column_range_filter
        self.timestamp_range_filter = timestamp_range_filter
        self.value_range_filter = value_range_filter
        self.cells_per_row_offset_filter = cells_per_row_offset_filter
        self.cells_per_row_limit_filter = cells_per_row_limit_filter
        self.cells_per_column_limit_filter = cells_per_column_limit_filter
        self.row_sample_filter = row_sample_filter
        self.strip_value_transformer = strip_value_transformer
        self._check_single_value()

    def _check_single_value(self):
        """Checks that exactly one value is set on the instance.

        :raises: :class:`TypeError <exceptions.TypeError>` if not exactly one
                 value set on the instance.
        """
        values_set = (
            int(self.row_key_regex_filter is not None) +
            int(self.family_name_regex_filter is not None) +
            int(self.column_qualifier_regex_filter is not None) +
            int(self.value_regex_filter is not None) +
            int(self.column_range_filter is not None) +
            int(self.timestamp_range_filter is not None) +
            int(self.value_range_filter is not None) +
            int(self.cells_per_row_offset_filter is not None) +
            int(self.cells_per_row_limit_filter is not None) +
            int(self.cells_per_column_limit_filter is not None) +
            int(self.row_sample_filter is not None) +
            int(self.strip_value_transformer is not None)
        )
        if values_set != 1:
            raise TypeError('Exactly one value must be set in a row filter')

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (
            other.row_key_regex_filter == self.row_key_regex_filter and
            other.family_name_regex_filter == self.family_name_regex_filter and
            (other.column_qualifier_regex_filter ==
             self.column_qualifier_regex_filter) and
            other.value_regex_filter == self.value_regex_filter and
            other.column_range_filter == self.column_range_filter and
            other.timestamp_range_filter == self.timestamp_range_filter and
            other.value_range_filter == self.value_range_filter and
            (other.cells_per_row_offset_filter ==
             self.cells_per_row_offset_filter) and
            (other.cells_per_row_limit_filter ==
             self.cells_per_row_limit_filter) and
            (other.cells_per_column_limit_filter ==
             self.cells_per_column_limit_filter) and
            other.row_sample_filter == self.row_sample_filter and
            other.strip_value_transformer == self.strip_value_transformer
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_pb(self):
        """Converts the :class:`RowFilter` to a protobuf.

        :rtype: :class:`.data_pb2.RowFilter`
        :returns: The converted current object.
        """
        self._check_single_value()
        row_filter_kwargs = {}
        if self.row_key_regex_filter is not None:
            row_filter_kwargs['row_key_regex_filter'] = _to_bytes(
                self.row_key_regex_filter)
        if self.family_name_regex_filter is not None:
            row_filter_kwargs['family_name_regex_filter'] = (
                self.family_name_regex_filter)
        if self.column_qualifier_regex_filter is not None:
            row_filter_kwargs['column_qualifier_regex_filter'] = _to_bytes(
                self.column_qualifier_regex_filter)
        if self.value_regex_filter is not None:
            row_filter_kwargs['value_regex_filter'] = _to_bytes(
                self.value_regex_filter)
        if self.column_range_filter is not None:
            row_filter_kwargs['column_range_filter'] = (
                self.column_range_filter.to_pb())
        if self.timestamp_range_filter is not None:
            row_filter_kwargs['timestamp_range_filter'] = (
                self.timestamp_range_filter.to_pb())
        if self.value_range_filter is not None:
            row_filter_kwargs['value_range_filter'] = (
                self.value_range_filter.to_pb())
        if self.cells_per_row_offset_filter is not None:
            row_filter_kwargs['cells_per_row_offset_filter'] = (
                self.cells_per_row_offset_filter)
        if self.cells_per_row_limit_filter is not None:
            row_filter_kwargs['cells_per_row_limit_filter'] = (
                self.cells_per_row_limit_filter)
        if self.cells_per_column_limit_filter is not None:
            row_filter_kwargs['cells_per_column_limit_filter'] = (
                self.cells_per_column_limit_filter)
        if self.row_sample_filter is not None:
            row_filter_kwargs['row_sample_filter'] = (
                self.row_sample_filter)
        if self.strip_value_transformer is not None:
            row_filter_kwargs['strip_value_transformer'] = (
                self.strip_value_transformer)
        return data_pb2.RowFilter(**row_filter_kwargs)


class TimestampRange(object):
    """Range of time with inclusive lower and exclusive upper bounds.

    :type start: :class:`datetime.datetime`
    :param start: (Optional) The (inclusive) lower bound of the timestamp
                  range. If omitted, defaults to Unix epoch.

    :type end: :class:`datetime.datetime`
    :param end: (Optional) The (exclusive) upper bound of the timestamp
                range. If omitted, defaults to "infinity" (no upper bound).
    """

    def __init__(self, start=None, end=None):
        self.start = start
        self.end = end

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (other.start == self.start and
                other.end == self.end)

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_pb(self):
        """Converts the :class:`TimestampRange` to a protobuf.

        :rtype: :class:`.data_pb2.TimestampRange`
        :returns: The converted current object.
        """
        timestamp_range_kwargs = {}
        if self.start is not None:
            timestamp_range_kwargs['start_timestamp_micros'] = (
                _timestamp_to_microseconds(self.start))
        if self.end is not None:
            timestamp_range_kwargs['end_timestamp_micros'] = (
                _timestamp_to_microseconds(self.end))
        return data_pb2.TimestampRange(**timestamp_range_kwargs)


class ColumnRange(object):
    """A range of columns to restrict to in a row filter.

    Both the start and end column can be included or excluded in the range.
    By default, we include them both, but this can be changed with optional
    flags.

    :type column_family_id: str
    :param column_family_id: The column family that contains the columns. Must
                             be of the form ``[_a-zA-Z0-9][-_.a-zA-Z0-9]*``.

    :type start_column: bytes
    :param start_column: The start of the range of columns. If no value is
                         used, it is interpreted as the empty string
                         (inclusive) by the backend.

    :type end_column: bytes
    :param end_column: The end of the range of columns. If no value is used, it
                       is interpreted as the infinite string (exclusive) by the
                       backend.

    :type inclusive_start: bool
    :param inclusive_start: Boolean indicating if the start column should be
                            included in the range (or excluded).

    :type inclusive_end: bool
    :param inclusive_end: Boolean indicating if the end column should be
                          included in the range (or excluded).
    """

    def __init__(self, column_family_id, start_column=None, end_column=None,
                 inclusive_start=True, inclusive_end=True):
        self.column_family_id = column_family_id
        self.start_column = start_column
        self.end_column = end_column
        self.inclusive_start = inclusive_start
        self.inclusive_end = inclusive_end

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (other.column_family_id == self.column_family_id and
                other.start_column == self.start_column and
                other.end_column == self.end_column and
                other.inclusive_start == self.inclusive_start and
                other.inclusive_end == self.inclusive_end)

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_pb(self):
        """Converts the :class:`ColumnRange` to a protobuf.

        :rtype: :class:`.data_pb2.ColumnRange`
        :returns: The converted current object.
        """
        column_range_kwargs = {'family_name': self.column_family_id}
        if self.start_column is not None:
            if self.inclusive_start:
                key = 'start_qualifier_inclusive'
            else:
                key = 'start_qualifier_exclusive'
            column_range_kwargs[key] = _to_bytes(self.start_column)
        if self.end_column is not None:
            if self.inclusive_end:
                key = 'end_qualifier_inclusive'
            else:
                key = 'end_qualifier_exclusive'
            column_range_kwargs[key] = _to_bytes(self.end_column)
        return data_pb2.ColumnRange(**column_range_kwargs)


class CellValueRange(object):
    """A range of values to restrict to in a row filter.

    With only match cells that have values in this range.

    Both the start and end value can be included or excluded in the range.
    By default, we include them both, but this can be changed with optional
    flags.

    :type start_value: bytes
    :param start_value: The start of the range of values. If no value is
                        used, it is interpreted as the empty string
                        (inclusive) by the backend.

    :type end_value: bytes
    :param end_value: The end of the range of values. If no value is used, it
                      is interpreted as the infinite string (exclusive) by the
                      backend.

    :type inclusive_start: bool
    :param inclusive_start: Boolean indicating if the start value should be
                            included in the range (or excluded).

    :type inclusive_end: bool
    :param inclusive_end: Boolean indicating if the end value should be
                          included in the range (or excluded).
    """

    def __init__(self, start_value=None, end_value=None,
                 inclusive_start=True, inclusive_end=True):
        self.start_value = start_value
        self.end_value = end_value
        self.inclusive_start = inclusive_start
        self.inclusive_end = inclusive_end

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (other.start_value == self.start_value and
                other.end_value == self.end_value and
                other.inclusive_start == self.inclusive_start and
                other.inclusive_end == self.inclusive_end)

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_pb(self):
        """Converts the :class:`CellValueRange` to a protobuf.

        :rtype: :class:`.data_pb2.ValueRange`
        :returns: The converted current object.
        """
        value_range_kwargs = {}
        if self.start_value is not None:
            if self.inclusive_start:
                key = 'start_value_inclusive'
            else:
                key = 'start_value_exclusive'
            value_range_kwargs[key] = _to_bytes(self.start_value)
        if self.end_value is not None:
            if self.inclusive_end:
                key = 'end_value_inclusive'
            else:
                key = 'end_value_exclusive'
            value_range_kwargs[key] = _to_bytes(self.end_value)
        return data_pb2.ValueRange(**value_range_kwargs)


class RowFilterChain(object):
    """Chain of row filters.

    Sends rows through several filters in sequence. The filters are "chained"
    together to process a row. After the first filter is applied, the second
    is applied to the filtered output and so on for subsequent filters.

    :type filters: list
    :param filters: List of :class:`RowFilter`, :class:`RowFilterChain`,
                    :class:`RowFilterUnion` and/or
                    :class:`ConditionalRowFilter`
    """

    def __init__(self, filters=None):
        self.filters = filters

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return other.filters == self.filters

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_pb(self):
        """Converts the :class:`RowFilterChain` to a protobuf.

        :rtype: :class:`.data_pb2.RowFilter`
        :returns: The converted current object.
        """
        chain = data_pb2.RowFilter.Chain(
            filters=[row_filter.to_pb() for row_filter in self.filters])
        return data_pb2.RowFilter(chain=chain)


class RowFilterUnion(object):
    """Union of row filters.

    Sends rows through several filters simultaneously, then
    merges / interleaves all the filtered results together.

    If multiple cells are produced with the same column and timestamp,
    they will all appear in the output row in an unspecified mutual order.

    :type filters: list
    :param filters: List of :class:`RowFilter`, :class:`RowFilterChain`,
                    :class:`RowFilterUnion` and/or
                    :class:`ConditionalRowFilter`
    """

    def __init__(self, filters=None):
        self.filters = filters

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return other.filters == self.filters

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_pb(self):
        """Converts the :class:`RowFilterUnion` to a protobuf.

        :rtype: :class:`.data_pb2.RowFilter`
        :returns: The converted current object.
        """
        interleave = data_pb2.RowFilter.Interleave(
            filters=[row_filter.to_pb() for row_filter in self.filters])
        return data_pb2.RowFilter(interleave=interleave)


class ConditionalRowFilter(object):
    """Conditional filter

    Executes one of two filters based on another filter. If the ``base_filter``
    returns any cells in the row, then ``true_filter`` is executed. If not,
    then ``false_filter`` is executed.

    .. note::

        The ``base_filter`` does not execute atomically with the true and false
        filters, which may lead to inconsistent or unexpected results.

        Additionally, executing a :class:`ConditionalRowFilter` has poor
        performance on the server, especially when ``false_filter`` is set.

    :type base_filter: :class:`RowFilter`, :class:`RowFilterChain`,
                       :class:`RowFilterUnion` or :class:`ConditionalRowFilter`
    :param base_filter: The filter to condition on before executing the
                        true/false filters.

    :type true_filter: :class:`RowFilter`, :class:`RowFilterChain`,
                       :class:`RowFilterUnion` or :class:`ConditionalRowFilter`
    :param true_filter: (Optional) The filter to execute if there are any cells
                        matching ``base_filter``. If not provided, no results
                        will be returned in the true case.

    :type false_filter: :class:`RowFilter`, :class:`RowFilterChain`,
                        :class:`RowFilterUnion` or
                        :class:`ConditionalRowFilter`
    :param false_filter: (Optional) The filter to execute if there are no cells
                         matching ``base_filter``. If not provided, no results
                         will be returned in the false case.
    """

    def __init__(self, base_filter, true_filter=None, false_filter=None):
        self.base_filter = base_filter
        self.true_filter = true_filter
        self.false_filter = false_filter

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (other.base_filter == self.base_filter and
                other.true_filter == self.true_filter and
                other.false_filter == self.false_filter)

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_pb(self):
        """Converts the :class:`ConditionalRowFilter` to a protobuf.

        :rtype: :class:`.data_pb2.RowFilter`
        :returns: The converted current object.
        """
        condition_kwargs = {'predicate_filter': self.base_filter.to_pb()}
        if self.true_filter is not None:
            condition_kwargs['true_filter'] = self.true_filter.to_pb()
        if self.false_filter is not None:
            condition_kwargs['false_filter'] = self.false_filter.to_pb()
        condition = data_pb2.RowFilter.Condition(**condition_kwargs)
        return data_pb2.RowFilter(condition=condition)


def _parse_rmw_row_response(row_response):
    """Parses the response to a ``ReadModifyWriteRow`` request.

    :type row_response: :class:`.data_pb2.Row`
    :param row_response: The response row (with only modified cells) from a
                         ``ReadModifyWriteRow`` request.

    :rtype: dict
    :returns: The new contents of all modified cells. Returned as a
              dictionary of column families, each of which holds a
              dictionary of columns. Each column contains a list of cells
              modified. Each cell is represented with a two-tuple with the
              value (in bytes) and the timestamp for the cell. For example:

              .. code:: python

                  {
                      u'col-fam-id': {
                          b'col-name1': [
                              (b'cell-val', datetime.datetime(...)),
                              (b'cell-val-newer', datetime.datetime(...)),
                          ],
                          b'col-name2': [
                              (b'altcol-cell-val', datetime.datetime(...)),
                          ],
                      },
                      u'col-fam-id2': {
                          b'col-name3-but-other-fam': [
                              (b'foo', datetime.datetime(...)),
                          ],
                      },
                  }
    """
    result = {}
    for column_family in row_response.families:
        column_family_id, curr_family = _parse_family_pb(column_family)
        result[column_family_id] = curr_family
    return result
