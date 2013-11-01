==============
Authentication
==============

The authentication to the REST API is done using HTTP Basic Auth.


Client
--------

Currently only the user of ID 0 (root) is allowed to access the API.


Examples
---------

Python
~~~~~~~

Get list of users::

    import requests

    print requests.get(
        'http://freenas.mydomain/api/v1.0/account/bsdusers/',
        auth=('root', 'freenas'),
    )
