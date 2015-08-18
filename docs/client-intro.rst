Base for Everything
===================

To use the API, the :class:`Client <gcloud_bigtable.client.Client>`
class defines a high-level interface which handles authorization
and creating other objects:

.. code:: python

    from gcloud_bigtable.client import Client
    client = Client()

Authorization
-------------

This will use the Google `Application Default Credentials`_ if
you don't pass any credentials of your own. If you are **familiar** with the
`oauth2client`_ library, you can create a ``credentials`` object and
pass it directly:

.. code:: python

    client = Client(credentials=credentials)

Project ID
----------

.. tip::

    Be sure to use the **Project ID**, not the **Project Number**.

You can also explicitly provide the ``project_id`` rather than relying
on the inferred value:

.. code:: python

    client = Client(project_id='my-cloud-console-project')

When implicit, the value is inferred from the environment in the following
order:

* The ``GCLOUD_PROJECT`` environment variable
* The Google App Engine application ID
* The Google Compute Engine project ID (from the metadata server)

Admin API Access
----------------

If you'll be using your client to make `Cluster Admin`_ and `Table Admin`_
API requests, you'll need to pass the ``admin`` argument:

.. code:: python

    client = Client(admin=True)

Read-Only Mode
--------------

If on the other hand, you only have (or want) read access to the data,
you can pass the ``read_only`` argument:

.. code:: python

    client = Client(read_only=True)

This will ensure that the
:data:`READ_ONLY_SCOPE <gcloud_bigtable.client.READ_ONLY_SCOPE>` is used
for API requests (so any accidental requests that would modify data will
fail).

.. _Application Default Credentials: https://developers.google.com/identity/protocols/application-default-credentials
.. _oauth2client: http://oauth2client.readthedocs.org/en/latest/
.. _Cluster Admin: https://github.com/GoogleCloudPlatform/cloud-bigtable-client/tree/f4d922bb950f1584b30f9928e84d042ad59f5658/bigtable-protos/src/main/proto/google/bigtable/admin/cluster/v1
.. _Table Admin: https://github.com/GoogleCloudPlatform/cloud-bigtable-client/tree/f4d922bb950f1584b30f9928e84d042ad59f5658/bigtable-protos/src/main/proto/google/bigtable/admin/table/v1