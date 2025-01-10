`cloudsync` plugin: Cloud Sync
==============================

.. contents:: Table of Contents
    :depth: 3

OAuth
-----

Some cloud providers offer the option to configure access using the standard OAuth flow through the user's browser.
The process works as follows:

* The UI opens a pop-up window with the URL: `https://truenas.com/oauth/<provider>?origin=<NAS IP>`
* The `truenas.com` web server proxies this request to an installation of the
  `oauth-portal <https://github.com/ixsystems/oauth-portal>`_.
* The OAuth portal forwards the request to the corresponding OAuth provider, retrieves the tokens, and returns them to
  the UI using `window.opener.postMessage`.
* The UI receives the tokens and populates the corresponding Cloud Credentials configuration form.
