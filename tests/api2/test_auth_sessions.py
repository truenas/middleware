from middlewared.test.integration.utils import call, client, password


def test_terminate_nonexistent_session_returns_false():
    """Terminating a session id that does not exist returns False rather than erroring."""
    assert call("auth.terminate_session", "not-a-real-session-id") is False


def test_logout_authenticated_session():
    """auth.logout tears down an authenticated session."""
    with client(auth=None) as c:
        resp = c.call(
            "auth.login_ex",
            {
                "mechanism": "PASSWORD_PLAIN",
                "username": "root",
                "password": password(),
            },
        )
        assert resp["response_type"] == "SUCCESS"
        session_id = c.call("auth.sessions", [["current", "=", True]], {"get": True})["id"]

        assert c.call("auth.logout") is True

        # The session is gone from the manager's point of view.
        assert call("auth.sessions", [["id", "=", session_id]]) == []
