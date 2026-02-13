SCRAM Authentication for API Keys
==================================

Overview
--------

TrueNAS middleware supports two authentication methods for API keys:

1. **Legacy PLAIN authentication** (``API_KEY_PLAIN``): Sends the raw API key directly to the server
2. **SCRAM-SHA-512 authentication** (``SCRAM``): Uses challenge-response authentication per RFC 5802 and RFC 7677

SCRAM authentication provides mutual authentication between client and server without transmitting
the raw key material during authentication. It is the recommended method for all implementations.

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
        c.call('auth.login', 'root', 'password')

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
- RFC 7677: SCRAM-SHA-256 and SCRAM-SHA-512 (TrueNAS uses SHA-512)
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

- ``n,,`` indicates no channel binding (GS2 header per RFC 5802 Section 7)
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

- ``c={channel-binding}`` is base64-encoded GS2 header (``biws`` which is base64 for ``n,,``)
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
- ``client-final-without-proof`` is the client final message without the proof (e.g., ``c=biws,r=...``)

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

Error Handling
--------------

Common error responses:

**AUTH_ERR response:**
  Invalid credentials, revoked key, or authentication failure.

**ENOTAUTHENTICATED:**
  Server signature verification failed - possible man-in-the-middle attack.

**Method does not exist:**
  Server doesn't support ``auth.login_ex`` (pre-SCRAM version). Use legacy ``auth.login_with_api_key`` method.

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

- RFC 7677: SCRAM-SHA-256 and SCRAM-SHA-512 Simple Authentication and Security Layer (SASL) Mechanisms

  https://datatracker.ietf.org/doc/html/rfc7677

- RFC 5234: Augmented BNF for Syntax Specifications: ABNF

  https://datatracker.ietf.org/doc/html/rfc5234

- TrueNAS API Client Library

  https://github.com/truenas/api_client
