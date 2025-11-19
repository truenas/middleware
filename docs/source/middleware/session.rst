Middleware session lifecycle
############################

.. contents:: Table of Contents
    :depth: 4


The middlewared process allows multiple concurrent authenticated client sessions. Depending on the origin of the client
connection an authenticated session may be automatically created for it.

Definitions
***********

Middleware session ID
=====================

For the purposes of this document the middleware session ID is a UUID generated when the middleware client connection
is accepted. This middleware session ID will exist prior to authentication and insertion of session into the middleware
session manager.


Session manager
===============

This refers to the SessionManager instance that is created in AuthService.service_manager in plugins/auth.py.
All authenticated sessions will have an entry in the session manager. Sessions in the session manager are keyed
by the middleware session ID.


Session manager credential
==========================

This refers to an instance of SessionManagerCredentials as defined in auth.py. A new session manager credential
instance is created when a client connection issues an `auth.login_ex` call. The session manager credential may
represent an interactive user session or a non-interactive backend operation. On successful authentication the
`app.authenticated_credentials` will be a reference to a valid authenticated, and logged in credentials object.
This object is used to authorize middleware method calls and subscriptions.


Token manager
=============

This refers to the TokenManager instance that is created in AuthService.token_manager in plugins/auth.py.
Authenticated sessions can create authentication tokens with varying characteristics and use them to re-authenticate
to the NAS. Tokens do not persist across middlewared restarts and are only for the current TrueNAS node on which they
are created. Tokens are keyed by their token string (which is returned to API clients when they generate the token).
See `middlewared.utils.crypto.generate_token`.


Token
=====

An authentication token is an internal middleware object that stores a reference to a root SessionManagerCredentials
object from which it derives authorization to the TrueNAS server. The originating credential can be retrieved through
the `root_credentials()` method of the token object. Tokens have various security-related attributes such as
a ttl, origin matching, and a single-use option. There are two primary use-cases for tokens:

1. webui - store low-value credential for re-authentication to the middleware backend in case of service interruption.
2. authentication for upload / download endpoints for file IO through the middlware backend.

Currently all authenticated credentials except ones for single-use passwords may create authentication tokens.


API key
=======

An API key is a persistent key used for backend authentication. API keys are linked to individual user accounts and
persist across reboots and upgrades. They may be used to authenticate to both active and passive storage controllers,
and with legacy REST API are used for bearer authentication.

API keys are stored using SCRAM-SHA512 key derivation (as defined in RFC5802), with salt, stored_key, server_key,
and iteration count stored in the database. API keys can be used with two authentication mechanisms:

1. **API_KEY_PLAIN**: The plain API key is sent directly. This is simpler but does not provide replay resistance.
2. **SCRAM**: Multi-step authentication exchange providing replay resistance and mutual authentication capability.
   Client libraries for SCRAM authentication are available at https://github.com/truenas/truenas_scram.


Connection origin
=================

From the standpoint of authentication and session lifecycles, there are three broad categories of client connection
origins when viewed from the context of authenticated sessions: unix socket origins, external TCP socket origins, and
TrueNAS node connection origins. See `utils/origin.py` for details and ConnectionOrigin dataclass. This is
covered in more depth in the "Connection origins" section below.


Authenticator
=============

An authenticator is an initialized instance of UserPamAuthenticator, UnixPamAuthenticator, TokenPamAuthenticator,
or APIKeyPamAuthenticator object. Authenticators are used to issue calls to the Linux Pluggable Authentication
Modules API. The sequence of PAM calls from middleware session startup until session teardown is:

Login steps
* pam_start() - Initialize PAM handle and conversation
* pam_authenticate() - attempt authentication with provided credentials
* pam_acct_mgmt() - Verify that account has not been disabled
* pam_open_session() - open an interactive session

The pam_open_session() call generates a session UUID that is used as the login_id for audit tracking purposes.
This UUID is stored in the authenticator's session_uuid attribute and copied to the SessionManagerCredentials
login_id field.

Logout steps
* pam_close_session() - close the interactive session
* pam_end() - close the PAM handle and free resources


Connection origins
******************

Unix socket origin
==================

Processes on the TrueNAS host may establish authenticated middleware sessions by using the truenas_api_client
to connect to the middlewared AF_UNIX socket at `/var/run/middlewared/middlewared.sock`. When the session is
established, the client is automatically authenticated to middleware using the client credentials used by the
peer process connected to the socket. See SO_PEERCRED in unix(7). If the peer process has an unset loginuid,
then the session will be treated by middlewared as an internal session. This makes the `login` and `logout`
stages of the authentication process no-ops (to avoid unnecessary churn in `utmp` and pam_modules). The
most typical reason for the loginuid to be unset for a process opening a middleware session is the `midclt`
client being used in a systemd unit.


TrueNAS node origin
===================

This is a special type of client TCP connection originating from the remote node in an HA pair. It establishes
an internal root session.


TCP origin
==========

These are remote session from external clients. Middleware connections from remote clients do not automatically
generate authenticated sessions. Typically the first API call a remote client should make after connection is
`auth.login_ex` with a valid authentication payload.


Adding a new authentication mechanism
*************************************

There are various steps that need to happen before adding a new authentication mechanism to the middlewared
backend. The constants defining available authentication mechanisms must be updated, the API schema must
be updated, a new MiddlewarePamFile may be required, a new UserPamAuthenticator class may be required,
and a new SessionManagerCredentials class may be required.


New MiddlewarePamFile
=====================

The MiddlewarePamFile class is defined in `utils/account/authenticator.py` and contains all middleware-related
PAM configuration files. There should be corresponding files in the `etc_files/pam.d` source directory.


New UserPamAuthenticator
========================

Generally, adding a new PAM file and setting it as the `service` in the `TrueNASAuthenticatorState` should be
sufficient. If the authentication method requires multiple round trips between the middleware client and backend
then more work may be required to properly implement `pam_conv(3)`.


New SessionManagerCredentials
=============================

We currently use the SessionManagerCredentials class name to in our auditing to record how the user authenticated
to the TrueNAS middleware.


API and constants
=================

The `AuthMech` class will need to be updated for the new authentication mechanism, and potentially one or more
new `AuthResp` types will need to be added as well. This should be detailed in a NEP design document since it
will become part of the stable TrueNAS API. The supported authentication mechanisms at different authenticator
assurance levels defined in `utils/auth.py` will also need to be updated to account for the new authentication
mechanism. Once these have been updated, then the API schema arguments for `auth.login_ex` and
`auth.login_ex_continue` will also need to be updated for the new authentication mechanism. Logic for all
new `AuthMech` types will also have to be added in `auth.login_ex` in `plugins/auth.py` so that the
authentication mechanism will properly login through the middleware session manager.


SCRAM authentication example
=============================

The SCRAM (Salted Challenge Response Authentication Mechanism) authentication was added following the process
above. This implementation provides an example of adding a multi-round-trip authentication mechanism that
requires stateful conversation between client and server:

1. **API Schema Updates**: Added `AuthSCRAM` to the login_data union in `AuthLoginExArgs`, and `AuthRespScram`
   to the result union in `AuthLoginExResult`. The SCRAM mechanism supports CLIENT_FIRST_MESSAGE and
   CLIENT_FINAL_MESSAGE types, with corresponding SERVER_FIRST_RESPONSE and SERVER_FINAL_RESPONSE types.

2. **Authenticator Changes**: The authenticator handles the SCRAM exchange through pam_truenas.so, which manages
   the server-side SCRAM state and validation using stored API key credentials (salt, stored_key, server_key,
   iterations).

3. **Stateful Authentication**: Unlike simple password authentication, SCRAM requires maintaining state between
   the CLIENT_FIRST_MESSAGE and CLIENT_FINAL_MESSAGE exchanges, demonstrating how to implement complex
   authentication flows in the middleware.


SCRAM JSON-RPC message exchange
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The SCRAM authentication involves three messages between client and server::

    # Step 1: Client sends CLIENT_FIRST_MESSAGE
    Client -> Server:
    {
        "method": "auth.login_ex",
        "params": [{
            "mechanism": "SCRAM",
            "scram_type": "CLIENT_FIRST_MESSAGE",
            "rfc_str": "n,,n=user:10,r=fyko+d2lbbFgONRv9qkxdawL"
        }]
    }

    # Step 2: Server responds with SERVER_FIRST_RESPONSE
    Server -> Client:
    {
        "result": {
            "response_type": "SCRAM_RESPONSE",
            "scram_type": "SERVER_FIRST_RESPONSE",
            "rfc_str": "r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,s=QSXCR+Q6sek8bf92,i=500000",
            "user_info": null
        }
    }

    # Step 3: Client sends CLIENT_FINAL_MESSAGE
    Client -> Server:
    {
        "method": "auth.login_ex_continue",
        "params": [{
            "mechanism": "SCRAM",
            "scram_type": "CLIENT_FINAL_MESSAGE",
            "rfc_str": "c=biws,r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,p=v0X8v3Bz2T0CJGbJQyF0X+HI4Ts="
        }]
    }

    # Step 4: Server responds with SERVER_FINAL_RESPONSE
    Server -> Client:
    {
        "result": {
            "response_type": "SCRAM_RESPONSE",
            "scram_type": "SERVER_FINAL_RESPONSE",
            "rfc_str": "v=rmF9pqV8S7suAoZWja4dJRkFsKQ=",
            "user_info": {
                "username": "user",
                "privilege": {...},
                ...
            }
        }
    }

The `rfc_str` fields follow the format specified in RFC5802. The username in the CLIENT_FIRST_MESSAGE includes
the API key ID (e.g., "user:10" where 10 is the API key database ID). Client libraries for handling these
exchanges are available at https://github.com/truenas/truenas_scram.
