==============
Authentication
==============

The authentication to the REST API is done using OAuth2.


Client
--------

Client logins must be added from the WebUI, under System -> API Clients.

A secret will be automatically generated once the client name is added.


Examples
---------

Python
~~~~~~~

Get list of users::

    import oauth2

    consumer = oauth.Consumer(
        key='myClient',
        secret='886e8991d4ae9a010656921b1011f2c400348d1d643edbc807c429bb30168b8a55670f9f22cf68610c0a9e277dd69151c48c15c18aa2dccb8bf8b057ca1187c1',
    )
    client = oauth.Client(consumer)

    content = client.request(
        'http://freenas.mydomain/api/v1.0/account/bsdusers/',
        method='GET',
        headers={'Content-Type': 'application/json'},
    )
    print content
