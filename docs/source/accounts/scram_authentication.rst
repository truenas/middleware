SCRAM Authentication for API Keys
==================================

Overview
--------

TrueNAS middleware supports two authentication methods for API keys:

1. **Legacy PLAIN authentication** (``API_KEY_PLAIN``): Sends the raw API key directly to the server
2. **SCRAM-SHA-512 authentication** (``SCRAM``): Uses the SCRAM challenge-response mechanism (RFC 5802; RFC 7677 defines the SHA-256 family that SCRAM-SHA-512 follows)

SCRAM authentication provides mutual authentication between client and server without transmitting
the raw key material during authentication. It is the recommended method for all implementations.

SCRAM also supports an optional, negotiated **channel binding** mode (SCRAM-PLUS, using the
RFC 5929 ``tls-server-end-point`` binding) that cryptographically ties an authentication exchange
to the server's TLS certificate, defeating a TLS-terminating man-in-the-middle. See
`Channel Binding (SCRAM-PLUS)`_ below for the protocol details and for examples of computing the
binding.

API Key Format
--------------

Starting with TrueNAS 26, creating an API key returns both the raw key and precomputed SCRAM data:

.. code-block:: python

    {
        "id": 1,
        "key": "1-uz8DhKHFhRIUQIvjzabPYtpy5wf1DJ3ZBLlDgNVhRAFT7Y6pJGUlm0n3apwxWEU4",
        "client_key": "5oN8IbtXz57BMyPcHzB7I833Co2es6k/ZRCs5mbpivU1g9TjflgP3QXlciAbrqrLjZAf5/T8D4fKQkbLAFAnog==",
        "stored_key": "xYz123...",
        "server_key": "aBc456...",
        "salt": "dEf789...",
        "iterations": 500000,
        # ... other fields
    }

**Raw API key format** (``key`` field)::

    {api_key_id}-{64_character_alphanumeric_string}

Example::

    1-uz8DhKHFhRIUQIvjzabPYtpy5wf1DJ3ZBLlDgNVhRAFT7Y6pJGUlm0n3apwxWEU4

The ``key`` field is only returned at creation time and cannot be retrieved later.
Store both the raw key and SCRAM data securely.

Using TrueNAS API Client
-------------------------

Installation
~~~~~~~~~~~~

.. code-block:: bash

    pip install truenas-api-client

Creating an API Key (TrueNAS 26+)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from truenas_api_client import Client
    import json

    # Authenticate with username/password or existing credentials
    with Client() as c:
        c.login_with_password('root', 'password')

        # Create new API key
        api_key_data = c.call('api_key.create', {
            'name': 'My Application Key',
            'username': 'root'
        })

        # Save all data for future use
        with open('/secure/path/my_api_key.json', 'w') as f:
            json.dump({
                'raw_key': api_key_data['key'],
                'api_key_id': api_key_data['id'],
                'client_key': api_key_data['client_key'],
                'stored_key': api_key_data['stored_key'],
                'server_key': api_key_data['server_key'],
                'salt': api_key_data['salt'],
                'iterations': api_key_data['iterations']
            }, f, indent=2)

The raw key (``raw_key``) can be used for legacy authentication or with older TrueNAS versions.
The SCRAM data (``api_key_id``, ``client_key``, etc.) provides optimal performance and should
be preferred for TrueNAS 26+.

Basic Authentication with Raw Key
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from truenas_api_client import Client

    # Using raw API key string (automatic SCRAM authentication if available)
    with Client('ws://truenas.local/api/current') as c:
        c.login_with_api_key('root', '1-uz8DhKHFhRIUQIvjzabPYtpy...')

        # Now authenticated, can make API calls
        pools = c.call('pool.query')

The ``login_with_api_key()`` method automatically detects server capabilities and uses SCRAM
authentication if available, falling back to PLAIN authentication for older servers.

Optimal Authentication with Precomputed Keys (TrueNAS 26+)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using precomputed SCRAM keys avoids expensive PBKDF2 computation (500,000 iterations) on each
authentication:

.. code-block:: python

    from truenas_api_client import Client

    # Using precomputed SCRAM data from TrueNAS 26+ api_key.create response
    # IMPORTANT: Path must be absolute
    with Client('ws://truenas.local/api/current') as c:
        c.login_with_api_key('root', '/secure/path/my_api_key.json')

        # Authentication is faster - no PBKDF2 computation needed
        pools = c.call('pool.query')

where ``/secure/path/my_api_key.json`` contains:

.. code-block:: json

    {
        "api_key_id": 1,
        "client_key": "5oN8IbtXz57BMyPcHzB7I833Co...",
        "stored_key": "xYz123...",
        "server_key": "aBc456...",
        "salt": "dEf789...",
        "iterations": 500000
    }

**Note:** The path must be absolute (e.g., ``/home/user/keys/api.json``). Relative paths are not supported.

Specifying Authentication Mechanism
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from truenas_api_client import Client
    from truenas_api_client.auth_api_key import APIKeyAuthMech

    with Client('ws://truenas.local/api/current') as c:
        # Force SCRAM authentication
        c.login_with_api_key('root', api_key, APIKeyAuthMech.SCRAM)

        # Force legacy PLAIN authentication
        c.login_with_api_key('root', api_key, APIKeyAuthMech.PLAIN)

        # Auto-detect (default - recommended)
        c.login_with_api_key('root', api_key, APIKeyAuthMech.AUTO)

Channel Binding with the API Client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When the connection is made over TLS (``wss://``), the client automatically engages SCRAM-PLUS
channel binding (RFC 5929 ``tls-server-end-point``): it reads the server certificate from the live
TLS socket, computes the binding, and folds it into the SCRAM proof. No extra configuration is
required, and it works even with ``verify_ssl=False`` (the certificate is still read from the
handshake):

.. code-block:: python

    from truenas_api_client import Client

    # Over wss:// the SCRAM exchange is automatically channel-bound to the server certificate.
    with Client('wss://truenas.local/api/current') as c:
        c.login_with_api_key('root', '1-uz8DhKHFhRIUQIvjzabPYtpy...')
        pools = c.call('pool.query')

The local AF_UNIX socket is exempt: it is not a TLS transport, so the client skips channel binding
and the server accepts the unbound exchange. Over a plain ``ws://`` network connection channel
binding cannot be honored, so the default (``channel_binding=True``) raises; pass
``channel_binding=False`` to authenticate with an unbound exchange there. See
`Channel Binding (SCRAM-PLUS)`_ below for the protocol details and for adding channel binding to a
custom client.

Using Key Files
~~~~~~~~~~~~~~~

API keys can be stored in files for better security. The client supports multiple formats.

**IMPORTANT:** File paths must be absolute (e.g., ``/home/user/.config/truenas/api_key.json``).
Relative paths are not supported.

**JSON format with raw key (works with any TrueNAS version):**

.. code-block:: json

    {
        "raw_key": "1-uz8DhKHFhRIUQIvjzabPYtpy5wf1DJ3ZBLlDgNVhRAFT7Y6pJGUlm0n3apwxWEU4"
    }

**JSON format with precomputed SCRAM keys (optimal for TrueNAS 26+):**

.. code-block:: json

    {
        "api_key_id": 1,
        "client_key": "5oN8IbtXz57BMyPcHzB7I833Co...",
        "stored_key": "xYz123...",
        "server_key": "aBc456...",
        "salt": "dEf789...",
        "iterations": 500000
    }

**INI format:**

.. code-block:: ini

    [TRUENAS_API_KEY]
    raw_key = 1-uz8DhKHFhRIUQIvjzabPYtpy5wf1DJ3ZBLlDgNVhRAFT7Y6pJGUlm0n3apwxWEU4

Or for precomputed keys:

.. code-block:: ini

    [TRUENAS_API_KEY]
    api_key_id = 1
    client_key = 5oN8IbtXz57BMyPcHzB7I833Co...
    stored_key = xYz123...
    server_key = aBc456...
    salt = dEf789...
    iterations = 500000

Usage with absolute file path:

.. code-block:: python

    import os

    with Client('ws://truenas.local/api/current') as c:
        # Use absolute path
        key_path = '/home/user/.config/truenas/api_key.json'
        c.login_with_api_key('root', key_path)

        # Or resolve to absolute path
        key_path = os.path.abspath('~/my_api_key.json')
        c.login_with_api_key('root', key_path)

Migrating Existing API Keys from Pre-TrueNAS 26
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have API keys created before TrueNAS 26, you only have the raw key format.
To get the precomputed SCRAM data for optimal performance, use the ``api_key.convert_raw_key`` API:

.. code-block:: python

    from truenas_api_client import Client
    import json

    # Authenticate with existing credentials
    with Client() as c:
        # Use existing raw key for authentication
        c.login_with_api_key('root', '1-uz8DhKHFhRIUQIvjzabPYtpy...')

        # Convert to precomputed SCRAM format
        raw_key = '1-uz8DhKHFhRIUQIvjzabPYtpy...'
        scram_data = c.call('api_key.convert_raw_key', raw_key)

        # Save precomputed data for future use (use absolute path)
        with open('/secure/path/api_key_scram.json', 'w') as f:
            json.dump(scram_data, f, indent=2)

    # Now use the precomputed data (avoids PBKDF2 computation)
    with Client('ws://truenas.local/api/current') as c:
        c.login_with_api_key('root', '/secure/path/api_key_scram.json')

**Note:** The ``api_key.convert_raw_key`` method preserves the original salt from the key,
ensuring the generated SCRAM data matches the server's stored credentials.

Custom Client Implementation
-----------------------------

For custom clients not using the TrueNAS API client library, you must implement the SCRAM
protocol manually using the ``auth.login_ex`` JSON-RPC method.

Protocol Overview
~~~~~~~~~~~~~~~~~

SCRAM authentication consists of three message exchanges:

1. **Client First Message**: Client sends username:api_key_id, nonce
2. **Server First Response**: Server responds with its nonce, salt, and iteration count
3. **Client Final Message**: Client sends proof of key possession
4. **Server Final Response**: Server confirms authentication and provides server signature

The protocol is defined in:

- RFC 5802: Salted Challenge Response Authentication Mechanism (SCRAM)
- RFC 7677: SCRAM-SHA-256 and SCRAM-SHA-256-PLUS (TrueNAS uses SHA-512)
- RFC 5234: Augmented BNF for Syntax Specifications (for message format)

**Important for API Key Authentication:** When constructing SCRAM RFC messages manually (for custom clients),
the username field must be formatted as ``{username}:{api_key_id}``. For example, if authenticating as user
``root`` with API key ID ``1``, the SCRAM username would be ``root:1``.

**Note:** If using the ``truenas_pyscram`` Python library, pass ``username`` and ``api_key_id`` as separate
parameters to ``ClientFirstMessage()``. The library handles the concatenation internally.

Message Format
~~~~~~~~~~~~~~

SCRAM messages use a comma-separated attribute=value format defined in RFC 5802 Section 5.

**Client First Message format:**

.. code-block:: text

    n,,n={username}:{api_key_id},r={client-nonce}

Example for user ``root`` with API key ID ``1``:

.. code-block:: text

    n,,n=root:1,r=fyko+d2lbbFgONRv9qkxdawL

Where:

- ``n,,`` is the GS2 header (RFC 5802 Section 7). ``n,,`` requests no channel binding; a
  channel-binding client sends ``p=tls-server-end-point,,`` instead (see
  `Channel Binding (SCRAM-PLUS)`_)
- ``n={username}:{api_key_id}`` specifies the username and API key ID concatenated with ``:``
- ``r={client-nonce}`` is a client-generated random nonce (base64-encoded, 32 bytes recommended)

**Server First Response format:**

.. code-block:: text

    r={server-nonce},s={salt},i={iteration-count}

Where:

- ``r={server-nonce}`` is client nonce + server nonce concatenated
- ``s={salt}`` is base64-encoded salt (16 bytes)
- ``i={iteration-count}`` is PBKDF2 iteration count (500,000 for TrueNAS)

**Client Final Message format:**

.. code-block:: text

    c={channel-binding},r={server-nonce},p={client-proof}

Where:

- ``c={channel-binding}`` is the base64-encoded GS2 header (``biws`` — base64 of ``n,,`` — when no
  channel binding is used; with channel binding it also carries the binding data, see
  `Channel Binding (SCRAM-PLUS)`_)
- ``r={server-nonce}`` matches server's nonce from first response
- ``p={client-proof}`` is base64-encoded client proof (see computation below)

**Server Final Response format:**

.. code-block:: text

    v={server-signature}

Where:

- ``v={server-signature}`` is base64-encoded server signature for client to verify

Cryptographic Computations
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Per RFC 5802 Section 3, the following computations are required:

.. code-block:: text

    SaltedPassword := PBKDF2-HMAC-SHA512(api_key, salt, iterations)
    ClientKey := HMAC-SHA512(SaltedPassword, "Client Key")
    StoredKey := SHA512(ClientKey)
    AuthMessage := client-first-bare + "," + server-first + "," + client-final-without-proof
    ClientSignature := HMAC-SHA512(StoredKey, AuthMessage)
    ClientProof := ClientKey XOR ClientSignature

    ServerKey := HMAC-SHA512(SaltedPassword, "Server Key")
    ServerSignature := HMAC-SHA512(ServerKey, AuthMessage)

Where:

- ``client-first-bare`` is the client first message without the GS2 header (e.g., ``n=root:1,r=...``)
- ``server-first`` is the complete server first response (e.g., ``r=...,s=...,i=...``)
- ``client-final-without-proof`` is the client final message without the proof (e.g., ``c=biws,r=...``).
  When channel binding is used, the binding is carried inside ``c=`` and is therefore covered by the
  proof automatically (see `Channel Binding (SCRAM-PLUS)`_)

**Using Precomputed Keys:** If you have precomputed SCRAM data from TrueNAS 26+ or from
``api_key.convert_raw_key``, you can skip the expensive PBKDF2 computation and use the
provided ``client_key``, ``stored_key``, and ``server_key`` directly.

Authentication Flow
~~~~~~~~~~~~~~~~~~~

1. **Check server capabilities:**

.. code-block:: json

    {
        "method": "auth.mechanism_choices",
        "params": []
    }

Response includes ``"SCRAM"`` if supported.

2. **Send Client First Message:**

.. code-block:: json

    {
        "method": "auth.login_ex",
        "params": [{
            "mechanism": "SCRAM",
            "scram_type": "CLIENT_FIRST_MESSAGE",
            "rfc_str": "n,,n=root:1,r=fyko+d2lbbFgONRv9qkxdawL"
        }]
    }

**Critical:** Note the username format ``root:1`` which combines username and API key ID.

Response:

.. code-block:: json

    {
        "response_type": "SCRAM_RESPONSE",
        "scram_type": "SERVER_FIRST_RESPONSE",
        "rfc_str": "r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,s=QSXCR+Q6sek8bf92,i=500000"
    }

3. **Send Client Final Message:**

Compute the client proof using the formulas above, then send:

.. code-block:: json

    {
        "method": "auth.login_ex",
        "params": [{
            "mechanism": "SCRAM",
            "scram_type": "CLIENT_FINAL_MESSAGE",
            "rfc_str": "c=biws,r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,p=v0X8v3Bz2T0CJGbJQyF0X+HI4Ts="
        }]
    }

Response:

.. code-block:: json

    {
        "response_type": "SCRAM_RESPONSE",
        "scram_type": "SERVER_FINAL_RESPONSE",
        "rfc_str": "v=rmF9pqV8S7suAoZWja4dJRkFsKQ="
    }

4. **Verify Server Signature:**

Compute ``ServerSignature`` using the formulas above and compare with the value from
``v={server-signature}``. If they don't match, reject the authentication.

Example: Go Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: go

    package main

    import (
        "crypto/hmac"
        "crypto/rand"
        "crypto/sha512"
        "encoding/base64"
        "fmt"
        "strconv"
        "strings"

        "golang.org/x/crypto/pbkdf2"
    )

    // ScramClient handles SCRAM-SHA-512 authentication for API keys
    type ScramClient struct {
        username      string
        apiKeyID      int
        rawKey        string
        clientNonce   string
        serverNonce   string
        salt          []byte
        iterations    int
        saltedPwd     []byte
        clientFirstBare string
        serverFirst   string
    }

    // NewScramClient creates a new SCRAM client with raw key
    func NewScramClient(username string, apiKeyID int, rawKey string) *ScramClient {
        return &ScramClient{
            username: username,
            apiKeyID: apiKeyID,
            rawKey:   rawKey,
        }
    }

    // generateNonce generates a cryptographically random base64-encoded nonce
    // RFC 5802 recommends at least 128 bits (16 bytes), TrueNAS uses 32 bytes
    func generateNonce() (string, error) {
        nonce := make([]byte, 32)
        if _, err := rand.Read(nonce); err != nil {
            return "", err
        }
        return base64.StdEncoding.EncodeToString(nonce), nil
    }

    // GetClientFirstMessage generates the client first message
    // Note: username is formatted as "{username}:{api_key_id}"
    func (sc *ScramClient) GetClientFirstMessage() (map[string]interface{}, error) {
        var err error
        sc.clientNonce, err = generateNonce()
        if err != nil {
            return nil, err
        }

        // Format username as "username:api_key_id" for API key authentication
        scramUsername := fmt.Sprintf("%s:%d", sc.username, sc.apiKeyID)

        // Store client-first-bare for AuthMessage computation later
        sc.clientFirstBare = fmt.Sprintf("n=%s,r=%s", scramUsername, sc.clientNonce)

        // Full client first message includes GS2 header
        rfcStr := fmt.Sprintf("n,,%s", sc.clientFirstBare)

        return map[string]interface{}{
            "scram_type": "CLIENT_FIRST_MESSAGE",
            "rfc_str":    rfcStr,
        }, nil
    }

    // ProcessServerFirstResponse parses and stores the server first response
    func (sc *ScramClient) ProcessServerFirstResponse(rfcStr string) error {
        // Store complete server-first for AuthMessage computation later
        sc.serverFirst = rfcStr

        // Parse: r={nonce},s={salt},i={iterations}
        parts := strings.Split(rfcStr, ",")
        for _, part := range parts {
            kv := strings.SplitN(part, "=", 2)
            if len(kv) != 2 {
                continue
            }

            switch kv[0] {
            case "r":
                sc.serverNonce = kv[1]
                // Verify server nonce starts with our client nonce
                if !strings.HasPrefix(sc.serverNonce, sc.clientNonce) {
                    return fmt.Errorf("server nonce doesn't start with client nonce")
                }
            case "s":
                var err error
                sc.salt, err = base64.StdEncoding.DecodeString(kv[1])
                if err != nil {
                    return fmt.Errorf("invalid salt encoding: %w", err)
                }
                // Validate salt length (TrueNAS requires exactly 16 bytes)
                if len(sc.salt) != 16 {
                    return fmt.Errorf("invalid salt length: %d bytes (must be 16)", len(sc.salt))
                }
            case "i":
                var err error
                sc.iterations, err = strconv.Atoi(kv[1])
                if err != nil {
                    return fmt.Errorf("invalid iteration count: %w", err)
                }
                // Validate iteration count bounds (TrueNAS: 50k - 5M)
                if sc.iterations < 50000 || sc.iterations > 5000000 {
                    return fmt.Errorf("iteration count out of range: %d (must be 50,000-5,000,000)",
                        sc.iterations)
                }
            }
        }

        // Compute salted password using PBKDF2
        sc.saltedPwd = pbkdf2.Key(
            []byte(sc.rawKey),
            sc.salt,
            sc.iterations,
            64, // SHA-512 output size
            sha512.New,
        )

        return nil
    }

    // GetClientFinalMessage generates the client final message with proof
    func (sc *ScramClient) GetClientFinalMessage() (map[string]interface{}, error) {
        // ClientKey = HMAC(SaltedPassword, "Client Key")
        clientKeyHmac := hmac.New(sha512.New, sc.saltedPwd)
        clientKeyHmac.Write([]byte("Client Key"))
        clientKey := clientKeyHmac.Sum(nil)

        // StoredKey = SHA512(ClientKey)
        storedKeyHash := sha512.Sum512(clientKey)
        storedKey := storedKeyHash[:]

        // Construct client-final-without-proof
        channelBinding := base64.StdEncoding.EncodeToString([]byte("n,,"))
        clientFinalWithoutProof := fmt.Sprintf("c=%s,r=%s", channelBinding, sc.serverNonce)

        // AuthMessage = client-first-bare + "," + server-first + "," + client-final-without-proof
        authMessage := fmt.Sprintf("%s,%s,%s",
            sc.clientFirstBare,
            sc.serverFirst,
            clientFinalWithoutProof)

        // ClientSignature = HMAC(StoredKey, AuthMessage)
        clientSigHmac := hmac.New(sha512.New, storedKey)
        clientSigHmac.Write([]byte(authMessage))
        clientSignature := clientSigHmac.Sum(nil)

        // ClientProof = ClientKey XOR ClientSignature
        clientProof := make([]byte, len(clientKey))
        for i := range clientKey {
            clientProof[i] = clientKey[i] ^ clientSignature[i]
        }

        rfcStr := fmt.Sprintf("%s,p=%s",
            clientFinalWithoutProof,
            base64.StdEncoding.EncodeToString(clientProof))

        return map[string]interface{}{
            "scram_type": "CLIENT_FINAL_MESSAGE",
            "rfc_str":    rfcStr,
        }, nil
    }

    // VerifyServerSignature verifies the server final response
    func (sc *ScramClient) VerifyServerSignature(rfcStr string) error {
        // Parse v={signature}
        if !strings.HasPrefix(rfcStr, "v=") {
            return fmt.Errorf("invalid server final message format")
        }

        serverSig, err := base64.StdEncoding.DecodeString(rfcStr[2:])
        if err != nil {
            return fmt.Errorf("invalid server signature encoding: %w", err)
        }

        // Reconstruct AuthMessage
        channelBinding := base64.StdEncoding.EncodeToString([]byte("n,,"))
        clientFinalWithoutProof := fmt.Sprintf("c=%s,r=%s", channelBinding, sc.serverNonce)
        authMessage := fmt.Sprintf("%s,%s,%s",
            sc.clientFirstBare,
            sc.serverFirst,
            clientFinalWithoutProof)

        // ServerKey = HMAC(SaltedPassword, "Server Key")
        serverKeyHmac := hmac.New(sha512.New, sc.saltedPwd)
        serverKeyHmac.Write([]byte("Server Key"))
        serverKey := serverKeyHmac.Sum(nil)

        // ServerSignature = HMAC(ServerKey, AuthMessage)
        serverSigHmac := hmac.New(sha512.New, serverKey)
        serverSigHmac.Write([]byte(authMessage))
        expectedSig := serverSigHmac.Sum(nil)

        // Verify signatures match using constant-time comparison
        if !hmac.Equal(serverSig, expectedSig) {
            return fmt.Errorf("server signature verification failed")
        }

        return nil
    }

Usage example:

.. code-block:: go

    func authenticate(client *jsonrpc.Client, username, apiKey string) error {
        // Parse API key: {id}-{key}
        parts := strings.SplitN(apiKey, "-", 2)
        if len(parts) != 2 {
            return fmt.Errorf("invalid API key format")
        }

        apiKeyID, err := strconv.Atoi(parts[0])
        if err != nil {
            return fmt.Errorf("invalid API key ID: %w", err)
        }
        rawKey := parts[1]

        // Create SCRAM client with username, API key ID, and raw key
        sc := NewScramClient(username, apiKeyID, rawKey)

        // Step 1: Send client first message
        // The username will be formatted as "username:api_key_id" internally
        clientFirst, err := sc.GetClientFirstMessage()
        if err != nil {
            return err
        }

        var resp1 map[string]interface{}
        err = client.Call("auth.login_ex", map[string]interface{}{
            "mechanism":  "SCRAM",
            "scram_type": clientFirst["scram_type"],
            "rfc_str":    clientFirst["rfc_str"],
        }, &resp1)
        if err != nil {
            return err
        }

        if resp1["response_type"] != "SCRAM_RESPONSE" {
            return fmt.Errorf("unexpected response type: %v", resp1["response_type"])
        }

        // Step 2: Process server response and send client final
        err = sc.ProcessServerFirstResponse(resp1["rfc_str"].(string))
        if err != nil {
            return err
        }

        clientFinal, err := sc.GetClientFinalMessage()
        if err != nil {
            return err
        }

        var resp2 map[string]interface{}
        err = client.Call("auth.login_ex", map[string]interface{}{
            "mechanism":  "SCRAM",
            "scram_type": clientFinal["scram_type"],
            "rfc_str":    clientFinal["rfc_str"],
        }, &resp2)
        if err != nil {
            return err
        }

        if resp2["response_type"] != "SCRAM_RESPONSE" {
            return fmt.Errorf("unexpected response type: %v", resp2["response_type"])
        }

        // Step 3: Verify server signature
        return sc.VerifyServerSignature(resp2["rfc_str"].(string))
    }

Channel Binding (SCRAM-PLUS)
----------------------------

How channel binding works
~~~~~~~~~~~~~~~~~~~~~~~~~~~

SCRAM-PLUS (the ``-PLUS`` mechanism variants in RFC 5802 / RFC 7677) cryptographically binds a
SCRAM exchange to the TLS channel it runs over, using *channel binding* as defined in RFC 5929.
TrueNAS implements the ``tls-server-end-point`` binding: a value derived from the server's leaf
TLS certificate. Folding this value into the SCRAM proof lets the server detect a TLS-terminating
man-in-the-middle — an attacker who proxies the TLS connection presents a different certificate, so
the binding the client computes will not match the one the server expects and authentication fails.

Channel binding is **optional and negotiated per exchange** (the API-key PAM stack runs in
``channel_binding=negotiate`` mode):

- A client that does not request binding (GS2 ``n,,`` header) authenticates normally, even when the
  server has a binding available. This preserves backward compatibility with older clients.
- A client that requires binding (GS2 ``p=tls-server-end-point`` header) is verified against the
  server's certificate, and a mismatch is rejected.

**TrueNAS-specific behavior:**

- TLS is terminated at the nginx reverse proxy in front of middleware, so the binding is a hash of
  the **public** UI certificate that nginx serves. middlewared publishes the active UI certificate's
  ``tls-server-end-point`` value where ``pam_truenas`` can read and verify against it, and refreshes
  it automatically when the UI certificate is changed or redeployed.
- Because the binding is only a hash of a public certificate, a cleartext client could replay it.
  middleware therefore **rejects a channel-binding request (GS2 ``p=``) that does not arrive over
  TLS**, returning ``AUTH_ERR`` for the CLIENT_FIRST_MESSAGE before any challenge is issued. Request
  channel binding over ``wss://`` only.
- The recommended binding for TLS 1.3 is ``tls-exporter`` (RFC 9266). TrueNAS currently implements
  ``tls-server-end-point`` (RFC 5929), which works across TLS versions and does not require the TLS
  library to expose a keying-material exporter.

Computing the tls-server-end-point value
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``tls-server-end-point`` value is the server's DER-encoded leaf certificate hashed with the
digest from the certificate's own signature algorithm, with one substitution from RFC 5929
Section 4.1: if that algorithm uses MD5 or SHA-1, SHA-256 is used instead. For example, a
certificate signed with ``sha256WithRSAEncryption`` yields ``SHA-256(DER)``, and one signed with
``ecdsa-with-SHA384`` yields ``SHA-384(DER)``. RSASSA-PSS is also supported: its hash is carried in
the signature parameters rather than the algorithm OID, so a PSS-SHA-256 certificate yields
``SHA-256(DER)``. RFC 5929 Section 4.1 leaves the binding undefined only for algorithms that use no
single signature hash — notably EdDSA (Ed25519/Ed448), whose hash is internal to the signature
scheme — and those are rejected.

The DER-encoded leaf certificate is read from the live TLS connection — for example
``ssl_socket.getpeercert(binary_form=True)`` in Python or ``conn.ConnectionState().PeerCertificates[0].Raw``
in Go. This is the certificate as actually presented in the handshake, which is the whole point of
the binding: it reflects whatever endpoint the client is really talking to.

**Python (recommended) — using** ``truenas_pyscram``:

.. code-block:: python

    import truenas_pyscram

    # cert_der: the DER-encoded leaf certificate from the live TLS connection,
    # e.g. ssl_socket.getpeercert(binary_form=True).
    binding = truenas_pyscram.compute_tls_server_end_point(cert_der)
    # `binding` is a CryptoDatum wrapping the raw binding bytes; bytes(binding) for the raw value.

**Python (from scratch) — for clients that cannot use** ``truenas_pyscram``:

.. code-block:: python

    import hashlib
    from cryptography import x509

    def compute_tls_server_end_point(cert_der: bytes) -> bytes:
        cert = x509.load_der_x509_certificate(cert_der)
        # `signature_hash_algorithm` is None for algorithms (e.g. Ed25519) that have no
        # separate hash; those have no defined tls-server-end-point binding.
        sig_hash = cert.signature_hash_algorithm
        if sig_hash is None:
            raise ValueError('tls-server-end-point is undefined for this signature algorithm')

        # RFC 5929 4.1: MD5 and SHA-1 are promoted to SHA-256.
        hash_name = 'sha256' if sig_hash.name in ('md5', 'sha1') else sig_hash.name
        return hashlib.new(hash_name, cert_der).digest()

(This example also handles RSASSA-PSS correctly: ``cryptography`` reads the hash from the PSS
signature parameters, so ``signature_hash_algorithm`` returns that hash rather than ``None`` — it is
``None`` only for EdDSA, the genuinely undefined case. TrueNAS UI certificates are RSA or ECDSA in
practice.)

**Go — computing the binding from the TLS connection:**

.. code-block:: go

    import (
        "crypto/sha256"
        "crypto/sha512"
        "crypto/x509"
        "fmt"
        "hash"
    )

    // computeTLSServerEndPoint returns the RFC 5929 tls-server-end-point channel
    // binding for a server leaf certificate: the DER certificate hashed with the
    // digest from its own signature algorithm, with MD5/SHA-1 promoted to SHA-256.
    func computeTLSServerEndPoint(cert *x509.Certificate) ([]byte, error) {
        var h hash.Hash
        switch cert.SignatureAlgorithm {
        case x509.MD5WithRSA, x509.SHA1WithRSA, x509.ECDSAWithSHA1: // RFC 5929 4.1: promoted
            h = sha256.New()
        case x509.SHA256WithRSA, x509.ECDSAWithSHA256, x509.SHA256WithRSAPSS:
            h = sha256.New()
        case x509.SHA384WithRSA, x509.ECDSAWithSHA384, x509.SHA384WithRSAPSS:
            h = sha512.New384()
        case x509.SHA512WithRSA, x509.ECDSAWithSHA512, x509.SHA512WithRSAPSS:
            h = sha512.New()
        default:
            // EdDSA (Ed25519/Ed448) has no separate signature hash, so its
            // tls-server-end-point binding is undefined (RFC 5929 4.1).
            return nil, fmt.Errorf("tls-server-end-point undefined for %s", cert.SignatureAlgorithm)
        }
        h.Write(cert.Raw)
        return h.Sum(nil), nil
    }

    // The leaf certificate comes from the established TLS connection:
    //     state := tlsConn.ConnectionState()
    //     binding, err := computeTLSServerEndPoint(state.PeerCertificates[0])

Channel binding on the wire
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Channel binding changes only two fields of the SCRAM exchange; everything else (the
``ClientKey``/``StoredKey``/``ServerKey``/``ServerSignature`` computations, the nonces, the proof
formula) is identical to the unbound flow.

1. The **GS2 header** in the client-first-message changes from the no-binding flag ``n`` to
   ``p=tls-server-end-point``:

   Unbound::

       n,,n=root:1,r=fyko+d2lbbFgONRv9qkxdawL

   Bound::

       p=tls-server-end-point,,n=root:1,r=fyko+d2lbbFgONRv9qkxdawL

2. The **c= attribute** in the client-final-message carries the GS2 header followed by the raw
   binding bytes, base64-encoded as a whole. The GS2 header here is the cbind flag plus its
   ``,,`` separator exactly as it appeared in client-first:

   Unbound — ``c=biws`` (``biws`` is base64 of ``n,,``)::

       c=biws,r=...,p=...

   Bound — ``c=`` is ``base64("p=tls-server-end-point,," + binding_bytes)``::

       c=<base64 of "p=tls-server-end-point,," followed by the raw binding bytes>,r=...,p=...

Because ``c=`` is part of ``client-final-without-proof``, which is part of the ``AuthMessage`` covered
by the client proof, the binding is authenticated by the same proof — there is no separate field for
it on the wire.

Adding channel binding to a custom client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Python** — ``truenas_pyscram`` builds both messages for you. Pass ``channel_binding_type`` to the
client-first (which sets the ``p=tls-server-end-point`` GS2 header) and the binding bytes to the
client-final (which folds them into ``c=``):

.. code-block:: python

    import truenas_pyscram

    cert_der = ssl_socket.getpeercert(binary_form=True)
    binding = truenas_pyscram.compute_tls_server_end_point(cert_der)

    client_first = truenas_pyscram.ClientFirstMessage(
        username='root', api_key_id=1,
        channel_binding_type=truenas_pyscram.CB_TLS_SERVER_END_POINT,
    )
    # ... send str(client_first) as the CLIENT_FIRST_MESSAGE rfc_str, receive the server-first ...
    server_first = truenas_pyscram.ServerFirstMessage(rfc_string=server_first_rfc_str)

    client_final = truenas_pyscram.ClientFinalMessage(
        client_first=client_first, server_first=server_first,
        client_key=client_key, stored_key=stored_key,
        channel_binding=binding,
    )
    # ... send str(client_final) as the CLIENT_FINAL_MESSAGE rfc_str ...

**Go** — extend the ``ScramClient`` from `Example: Go Implementation`_ with a ``channelBinding``
field, then make these two changes. In ``GetClientFirstMessage`` choose the GS2 header from whether a
binding is present:

.. code-block:: go

    gs2Header := "n,,"
    if sc.channelBinding != nil {
        gs2Header = "p=tls-server-end-point,,"
    }
    sc.clientFirstBare = fmt.Sprintf("n=%s,r=%s", scramUsername, sc.clientNonce)
    rfcStr := gs2Header + sc.clientFirstBare

In ``GetClientFinalMessage`` (and the matching reconstruction in ``VerifyServerSignature``) build the
``c=`` value from the same GS2 header plus the raw binding bytes:

.. code-block:: go

    // cbind-input = gs2-header + cbind-data (RFC 5802 Section 6)
    cbindInput := []byte("n,,")
    if sc.channelBinding != nil {
        cbindInput = append([]byte("p=tls-server-end-point,,"), sc.channelBinding...)
    }
    channelBinding := base64.StdEncoding.EncodeToString(cbindInput)
    clientFinalWithoutProof := fmt.Sprintf("c=%s,r=%s", channelBinding, sc.serverNonce)

Set ``sc.channelBinding`` from ``computeTLSServerEndPoint()`` (above) once the TLS connection is
established and before sending the client-first-message.

Verifying behavior
~~~~~~~~~~~~~~~~~~~

The negotiated, TLS-only semantics produce three observable outcomes:

- An **unbound** login (GS2 ``n,,``) succeeds even when the server has a binding published — binding
  is negotiated, not required.
- A **bound** login (GS2 ``p=tls-server-end-point``) over ``wss://`` succeeds only when the client's
  computed binding matches the certificate nginx serves; a mismatch fails.
- A **bound request over plain** ``ws://`` is rejected at the CLIENT_FIRST_MESSAGE with ``AUTH_ERR``,
  because the binding cannot be honored on a non-TLS transport.


Security Considerations
-----------------------

1. **Never log or display sensitive data**: Raw API keys, SCRAM keys (client_key, server_key, stored_key),
   and salts are all cryptographic secrets equivalent to passwords. Never log, display, or transmit them
   over insecure channels.

2. **Use TLS/WSS**: Always use encrypted transport (``wss://`` not ``ws://``) to prevent eavesdropping
   and man-in-the-middle attacks.

3. **Store keys securely**:

   - Use appropriate file permissions (mode 0600) for key files
   - Consider using system keychains or secret management services
   - Never commit keys to version control

4. **Precomputed keys security**: While precomputed SCRAM keys avoid PBKDF2 computation, they still
   provide full authentication capability. Protect them with the same security as raw keys.

5. **Nonce generation**: Client nonces MUST be cryptographically random and unique per authentication
   attempt. Use your platform's cryptographically secure random number generator (e.g., ``crypto/rand``
   in Go, ``secrets`` module in Python).

6. **Server signature verification**: ALWAYS verify the server signature to prevent man-in-the-middle
   attacks. A valid server signature proves the server possesses the correct credentials.

7. **Constant-time comparison**: When comparing signatures or proofs, use constant-time comparison
   functions (e.g., ``hmac.Equal()`` in Go, ``hmac.compare_digest()`` in Python) to prevent timing attacks.

8. **Channel binding is negotiated, not downgrade-proof**: Per RFC 5802 Section 7, SCRAM does not
   protect against downgrade of channel binding types, and the API-key stack runs in ``negotiate``
   mode with a single ``SCRAM`` mechanism (no ``-PLUS`` name to advertise), so the server cannot
   detect a channel-binding-capable client that is steered to an unbound ``n,,`` exchange. Enforcing
   channel binding is therefore the **client's** responsibility: the TrueNAS API client binds by
   default over TLS and refuses to silently fall back to an unbound or plaintext exchange.

Error Handling
--------------

Common error responses:

**AUTH_ERR response:**
  Invalid credentials, revoked key, or authentication failure.

**ENOTAUTHENTICATED:**
  Server signature verification failed - possible man-in-the-middle attack.

**Method does not exist:**
  Server doesn't support ``auth.login_ex`` (pre-SCRAM version). The legacy ``auth.login_with_api_key``
  method may still be available on those older servers (it was removed from the v27 API). Custom
  clients that need to support older servers can use ``auth.login_with_api_key`` as a fallback for
  pre-25.04 versions while preferring ``auth.login_ex`` for modern servers.

**Invalid nonce:**
  Server nonce doesn't start with client nonce - protocol violation.

API Reference
-------------

API Method: api_key.create
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Creates a new API key. Starting with TrueNAS 26, returns both raw key and precomputed SCRAM data.

**Parameters:**

- ``name`` (string): Human-readable name for the API key
- ``username`` (string): Username to associate with the key
- ``expires_at`` (datetime, optional): Expiration timestamp

**Returns (TrueNAS 26+):**

Dictionary containing:

- ``id`` (int): The API key ID
- ``key`` (string): Raw API key in format ``{id}-{64_chars}`` (only returned at creation)
- ``client_key`` (string): Base64-encoded SCRAM ClientKey (only returned at creation)
- ``stored_key`` (string, secret): Base64-encoded SCRAM StoredKey
- ``server_key`` (string, secret): Base64-encoded SCRAM ServerKey
- ``salt`` (string, secret): Base64-encoded salt
- ``iterations`` (int): PBKDF2 iteration count (500,000)
- Additional metadata fields

**Example:**

.. code-block:: python

    api_key = client.call('api_key.create', {
        'name': 'Production App Key',
        'username': 'root'
    })

    # Save both raw and SCRAM data
    print(f"Raw key: {api_key['key']}")
    print(f"API key ID: {api_key['id']}")

**Roles Required:**

- ``API_KEY_WRITE``

API Method: api_key.convert_raw_key
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Converts a raw API key (from pre-TrueNAS 26 installations) into precomputed SCRAM components.
This method preserves the original salt to ensure compatibility with stored credentials.

**Parameters:**

- ``raw_key`` (string, Secret): The raw API key in format ``{id}-{key}``

**Returns:**

Dictionary containing:

- ``api_key_id`` (int): The API key ID
- ``iterations`` (int): PBKDF2 iteration count (500,000)
- ``salt`` (string): Base64-encoded salt
- ``client_key`` (string): Base64-encoded SCRAM ClientKey
- ``stored_key`` (string): Base64-encoded SCRAM StoredKey
- ``server_key`` (string): Base64-encoded SCRAM ServerKey

**Example:**

.. code-block:: python

    # For keys created before TrueNAS 26
    old_key = '1-uz8DhKHFhRIUQIvjzabPYtpy...'
    scram_data = client.call('api_key.convert_raw_key', old_key)

    # Save for future use (absolute path required)
    with open('/secure/path/scram_key.json', 'w') as f:
        json.dump(scram_data, f)

**Roles Required:**

- ``API_KEY_READ``

References
----------

- RFC 5802: Salted Challenge Response Authentication Mechanism (SCRAM) SASL and GSS-API Mechanisms

  https://datatracker.ietf.org/doc/html/rfc5802

- RFC 7677: SCRAM-SHA-256 and SCRAM-SHA-256-PLUS Simple Authentication and Security Layer (SASL) Mechanisms

  https://datatracker.ietf.org/doc/html/rfc7677

- RFC 5929: Channel Bindings for TLS (defines ``tls-server-end-point``, used for SCRAM-PLUS)

  https://datatracker.ietf.org/doc/html/rfc5929

- RFC 9266: Channel Bindings for TLS 1.3 (defines ``tls-exporter``)

  https://datatracker.ietf.org/doc/html/rfc9266

- RFC 5234: Augmented BNF for Syntax Specifications: ABNF

  https://datatracker.ietf.org/doc/html/rfc5234

- TrueNAS SCRAM Library (C and Python client-side primitives, incl. channel binding)

  https://github.com/truenas/truenas_scram

- TrueNAS API Client Library

  https://github.com/truenas/api_client
