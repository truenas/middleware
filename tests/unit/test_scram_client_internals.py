import pytest
import hashlib
import hmac
from base64 import b64encode, b64decode

from truenas_api_client.scram_impl import (
    TNScramAuthMessage,
    TNScramAuthResponse,
    ClientFirstMessage,
    ServerFirstMessage,
    ClientFinalMessage,
    ServerFinalMessage,
    generate_scram_nonce,
    hi,
    h,
    hmac_sha512,
    create_scram_client_key,
    create_scram_server_key,
    create_scram_auth_message,
    TNScramClient,
    TNScramData,
    TNScramServer,
)


# Test fixtures with specific credentials
@pytest.fixture
def test_credentials():
    """Test credentials for user 'bob' with specific SCRAM parameters"""
    return {
        'username': 'bob',
        'key_data': 'VqZfWCloeIoYsJbquX7BGaD45JBtOUx0NFHxg5ll7e4QLH1cG5XTtdGU0KbBxxRL',
        'iterations': 500000,
        'salt_b64': 'V05HWnZGSDBDT1M3Q3BxWQ==',
        'salted_password_b64': 'DJD4XD78r4eA6S6mSiQv2rF/GVnf2zjACIRBZiN4g60m+AHOW5NQFy57BJQKevSK523G3JLR8rSJ7SOu2IYmMA==',
        'api_key_id': 1,
        'api_key': '1-VqZfWCloeIoYsJbquX7BGaD45JBtOUx0NFHxg5ll7e4QLH1cG5XTtdGU0KbBxxRL'
    }


@pytest.fixture
def scram_client(test_credentials):
    """Create a TNScramClient with test credentials"""
    return TNScramClient(test_credentials['api_key'])


@pytest.fixture
def scram_server(test_credentials):
    """Create a TNScramServer with pre-computed keys for test credentials"""
    salt = b64decode(test_credentials['salt_b64'])
    salted_password = b64decode(test_credentials['salted_password_b64'])

    # Compute StoredKey and ServerKey from the SaltedPassword
    client_key = create_scram_client_key(salted_password)
    stored_key = h(client_key)
    server_key = create_scram_server_key(salted_password)

    server_data = TNScramData(
        algorithm='sha512',
        salt=salt,
        iteration_count=test_credentials['iterations'],
        stored_key=stored_key,
        server_key=server_key
    )

    return TNScramServer(server_data)


class TestEnums:
    def test_tn_scram_auth_message_values(self):
        assert TNScramAuthMessage.API_KEY_SCRAM == 'API_KEY_SCRAM'
        assert TNScramAuthMessage.API_KEY_SCRAM_FINAL == 'API_KEY_SCRAM_FINAL'

    def test_tn_scram_auth_response_values(self):
        assert TNScramAuthResponse.SCRAM_RESP_INIT == 'SCRAM_RESP_INIT'
        assert TNScramAuthResponse.SCRAM_RESP_FINAL == 'SCRAM_RESP_FINAL'


class TestDataClasses:
    def test_client_first_message_to_rfc_string(self):
        msg = ClientFirstMessage(
            api_key_id=7,
            username="bob",
            nonce="testnonce"
        )
        expected = "n=bob,r=testnonce"
        assert msg.to_rfc_string() == expected

    def test_server_first_message_to_rfc_string(self):
        msg = ServerFirstMessage(
            salt="OU9jM3RlbjBjZUNFUk1QLw==",
            iteration_count=50000,
            nonce="clientnonce_servernonce"
        )
        expected = "r=clientnonce_servernonce,s=OU9jM3RlbjBjZUNFUk1QLw==,i=50000"
        assert msg.to_rfc_string() == expected

    def test_client_final_message_to_rfc_string_with_proof(self):
        msg = ClientFinalMessage(
            channel_binding=None,
            nonce="testnonce",
            client_proof="testproof="
        )
        expected = "c=biws,r=testnonce,p=testproof="
        assert msg.to_rfc_string() == expected

    def test_client_final_message_to_rfc_string_without_proof(self):
        msg = ClientFinalMessage(
            channel_binding="biws",
            nonce="testnonce",
            client_proof=None
        )
        expected = "c=biws,r=testnonce"
        assert msg.to_rfc_string() == expected

    def test_client_final_message_default_channel_binding(self):
        msg = ClientFinalMessage(
            channel_binding=None,
            nonce="testnonce",
            client_proof="testproof="
        )
        expected = "c=biws,r=testnonce,p=testproof="
        assert msg.to_rfc_string() == expected


class TestCryptographicFunctions:
    def test_generate_scram_nonce(self):
        nonce1 = generate_scram_nonce()
        nonce2 = generate_scram_nonce()

        # Should be different each time
        assert nonce1 != nonce2

        # Should be valid base64 with 32 bytes of random data
        decoded = b64decode(nonce1)
        assert len(decoded) == 32

    def test_hi_function_with_test_credentials(self, test_credentials):
        """Test PBKDF2 with our specific test credentials"""
        key_data = test_credentials['key_data'].encode()
        salt = b64decode(test_credentials['salt_b64'])
        iterations = test_credentials['iterations']

        result = hi(key_data, salt, iterations)
        expected = b64decode(test_credentials['salted_password_b64'])

        assert result == expected

    def test_h_function(self):
        data = b"test data"
        result = h(data)

        expected = hashlib.sha512(data).digest()
        assert result == expected
        assert len(result) == 64

    def test_hmac_sha512(self):
        key = b"test key"
        data = b"test data"
        result = hmac_sha512(key, data)

        expected = hmac.new(key, data, hashlib.sha512).digest()
        assert result == expected
        assert len(result) == 64

    def test_create_scram_client_key(self, test_credentials):
        salted_password = b64decode(test_credentials['salted_password_b64'])
        result = create_scram_client_key(salted_password)

        expected = hmac_sha512(salted_password, b'Client Key')
        assert result == expected

    def test_create_scram_server_key(self, test_credentials):
        salted_password = b64decode(test_credentials['salted_password_b64'])
        result = create_scram_server_key(salted_password)

        expected = hmac_sha512(salted_password, b'Server Key')
        assert result == expected


class TestTNScramClient:
    def test_init_with_test_credentials(self, scram_client, test_credentials):
        assert scram_client.api_key_id == test_credentials['api_key_id']
        assert scram_client.api_key_data == test_credentials['key_data']
        assert scram_client.auth_message is None
        assert scram_client.client_first_message is None

    def test_init_invalid_api_key_format(self):
        with pytest.raises(ValueError):
            TNScramClient("invalid_key_format")

    def test_init_non_numeric_id(self):
        with pytest.raises(ValueError):
            TNScramClient("abc-test_key_data")

    def test_get_client_first_message(self, scram_client, test_credentials):
        result = scram_client.get_client_first_message(test_credentials['username'])

        assert isinstance(result, ClientFirstMessage)
        assert result.api_key_id == test_credentials['api_key_id']
        assert result.username == test_credentials['username']
        assert result.nonce is not None
        assert len(b64decode(result.nonce)) == 32
        assert scram_client.client_first_message == result

    def test_get_client_final_message(self, scram_client, test_credentials):
        # Set up client first message
        scram_client.client_first_message = ClientFirstMessage(
            api_key_id=test_credentials['api_key_id'],
            username=test_credentials['username'],
            nonce="clientnonce"
        )

        server_resp = ServerFirstMessage(
            salt=test_credentials['salt_b64'],
            iteration_count=test_credentials['iterations'],
            nonce="clientnonce_servernonce"
        )

        result = scram_client.get_client_final_message(server_resp, None)

        assert isinstance(result, ClientFinalMessage)
        assert result.nonce == "clientnonce_servernonce"
        assert result.client_proof is not None
        assert result.channel_binding is None
        assert scram_client.auth_message is not None
        assert scram_client.salted_api_key is not None

    def test_verify_server_final_message_success(self, scram_client, test_credentials):
        # Set up authentication state
        salted_password = b64decode(test_credentials['salted_password_b64'])
        scram_client.salted_api_key = salted_password
        scram_client.auth_message = "test_auth_message"

        # Create a valid server signature
        server_key = create_scram_server_key(salted_password)
        expected_signature = hmac_sha512(server_key, scram_client.auth_message.encode())

        server_resp = ServerFinalMessage(
            signature=b64encode(expected_signature).decode()
        )

        result = scram_client.verify_server_final_message(server_resp)
        assert result is True

    def test_verify_server_final_message_invalid_signature(self, scram_client, test_credentials):
        salted_password = b64decode(test_credentials['salted_password_b64'])
        scram_client.salted_api_key = salted_password
        scram_client.auth_message = "test_auth_message"

        server_resp = ServerFinalMessage(
            signature=b64encode(b"invalid_signature_data_here").decode()
        )

        result = scram_client.verify_server_final_message(server_resp)
        assert result is False

    def test_verify_server_final_message_no_signature(self, scram_client):
        scram_client.salted_api_key = b"test"
        scram_client.auth_message = "test"

        server_resp = ServerFinalMessage(signature="")

        with pytest.raises(ValueError, match="Server response lacks signature"):
            scram_client.verify_server_final_message(server_resp)


class TestTNScramServer:
    def test_get_server_first_message(self, scram_server, test_credentials):
        client_msg = ClientFirstMessage(
            api_key_id=test_credentials['api_key_id'],
            username=test_credentials['username'],
            nonce="client_nonce"
        )

        result = scram_server.get_server_first_message(client_msg)

        assert isinstance(result, ServerFirstMessage)
        assert result.salt == test_credentials['salt_b64']
        assert result.iteration_count == test_credentials['iterations']
        assert "client_nonce" in result.nonce
        assert len(result.nonce) > len("client_nonce")
        assert scram_server.client_first_message == client_msg
        assert scram_server.server_first_message == result

    def test_get_server_final_message_success(self, scram_server, test_credentials):
        # Set up the complete authentication flow using our test data
        salted_password = b64decode(test_credentials['salted_password_b64'])
        client_key = create_scram_client_key(salted_password)

        # Set up messages
        client_first = ClientFirstMessage(
            api_key_id=test_credentials['api_key_id'],
            username=test_credentials['username'],
            nonce="client_nonce"
        )

        server_first = ServerFirstMessage(
            salt=test_credentials['salt_b64'],
            iteration_count=test_credentials['iterations'],
            nonce="client_nonce_server_nonce"
        )

        scram_server.client_first_message = client_first
        scram_server.server_first_message = server_first

        # Create auth message
        client_final_no_proof = ClientFinalMessage(
            channel_binding="biws",
            nonce="client_nonce_server_nonce",
            client_proof=None
        )

        auth_message = create_scram_auth_message(
            client_first,
            server_first,
            client_final_no_proof
        )

        # Create valid client proof
        client_signature = hmac_sha512(scram_server.data.stored_key, auth_message.encode())
        client_proof = bytes(a ^ b for a, b in zip(client_key, client_signature))

        client_final = ClientFinalMessage(
            channel_binding="biws",
            nonce="client_nonce_server_nonce",
            client_proof=b64encode(client_proof).decode()
        )

        result = scram_server.get_server_final_message(client_final)

        assert isinstance(result, ServerFinalMessage)
        assert result.signature is not None

        # Verify the signature is correct
        expected_signature = hmac_sha512(scram_server.data.server_key, auth_message.encode())
        actual_signature = b64decode(result.signature)
        assert hmac.compare_digest(expected_signature, actual_signature)

    def test_get_server_final_message_invalid_proof(self, scram_server, test_credentials):
        client_first = ClientFirstMessage(
            api_key_id=test_credentials['api_key_id'],
            username=test_credentials['username'],
            nonce="client_nonce"
        )

        server_first = ServerFirstMessage(
            salt=test_credentials['salt_b64'],
            iteration_count=test_credentials['iterations'],
            nonce="client_nonce_server_nonce"

        scram_server.client_first_message = client_first
        scram_server.server_first_message = server_first

        client_final = ClientFinalMessage(
            channel_binding="biws",
            nonce="client_nonce_server_nonce",
            client_proof=b64encode(b"a" * 64).decode()  # 64 bytes to match SHA-512 output length
        )

        result = scram_server.get_server_final_message(client_final)
        assert result is None


class TestCompleteAuthenticationFlow:
    def test_end_to_end_authentication(self, scram_client, scram_server, test_credentials):
        """Test complete SCRAM authentication flow with test credentials"""

        # Step 1: Client first message
        client_first = scram_client.get_client_first_message(test_credentials['username'])
        assert isinstance(client_first, ClientFirstMessage)

        # Step 2: Server first message  
        server_first = scram_server.get_server_first_message(client_first)
        assert isinstance(server_first, ServerFirstMessage)

        # Step 3: Client final message
        client_final = scram_client.get_client_final_message(server_first, None)
        assert isinstance(client_final, ClientFinalMessage)

        # Step 4: Server final message
        server_final = scram_server.get_server_final_message(client_final)
        assert isinstance(server_final, ServerFinalMessage)

        # Step 5: Client verifies server
        verification_result = scram_client.verify_server_final_message(server_final)
        assert verification_result is True
