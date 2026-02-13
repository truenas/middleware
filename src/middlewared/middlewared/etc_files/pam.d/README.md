# TrueNAS PAM Configuration Files

This directory contains PAM (Pluggable Authentication Modules) configuration files used by TrueNAS middleware for
authentication and session management.

## Main PAM Services

### `/etc/pam.d/truenas`

Used for standard username/password authentication through the Web UI and API.

**Authentication flow:**
- When directory service authentication is enabled (licensed feature): Uses directory service provider
  (Active Directory, LDAP, FreeIPA)
- When directory service authentication is disabled: Uses local Unix authentication
- Faillock support is enabled when STIG mode is active (independent of directory services)
- Supports optional 2FA via OATH TOTP when enabled
- Includes account validation and session management
- Password changes are denied through this service

**Use this service when:** Authenticating users through the Web UI or API with username and password
credentials.

### `/etc/pam.d/truenas-api-key`

Used for authentication with API keys and SCRAM credentials.

**Authentication flow:**
- Authenticates via `pam_truenas.so` with support for:
  - Raw API key authentication
  - SCRAM-SHA512 authentication (requires multistep PAM conversation)
- Includes account validation based on directory service configuration
- Faillock support is enabled when STIG mode is active
- Password changes are denied through this service

**Use this service when:** Authenticating API requests using API keys or SCRAM-SHA512 authentication.

### `/etc/pam.d/truenas-unix`

Used for authentication via Unix socket, delegating authentication to the calling application.

**Authentication flow:**
- Uses `pam_access.so` for access control
- No password verification - delegates authentication to the calling application
- Includes account validation based on directory service configuration
- Password changes are denied through this service

**Use this service when:**
- Authenticating internal middleware connections where the calling application has already authenticated the user
  (e.g., file upload/download tokens)
- The application uses SO_PEERCRED to validate identity of AF_UNIX connections
- The application implements an authentication protocol not currently supported in the PAM layer
  (e.g., passkey)

**Security note:** This service should not be used without robust security evaluation of the calling application,
as it trusts the application to have performed authentication.

## Session Management

All three TrueNAS PAM services (`truenas`, `truenas-api-key`, `truenas-unix`) support session management through
the shared `/etc/pam.d/truenas-session` configuration.

**Important:** Applications using these PAM services should call `pam_open_session()` and `pam_close_session()` to
properly manage sessions. This ensures that sessions appear in the `system.security.sessions` output and are
tracked correctly by the middleware.

## Supporting Files

- `truenas-session.mako` - Session management configuration included by all three main PAM services
- `common-auth.mako` - Common authentication modules for directory service integration
- `common-auth-unix.mako` - Unix authentication modules
- `common-account.mako` - Account validation modules
- `common-password.mako` - Password management modules
- `common-session.mako` - Session management modules
- `common-session-noninteractive.mako` - Non-interactive session modules
- `sshd_linux.mako` - SSH daemon PAM configuration

## Implementation Details

All `.mako` files are templates that are rendered during system configuration to generate the actual PAM
configuration files in `/etc/pam.d/`. The rendering incorporates system settings such as:

- Directory service authentication state (licensed feature)
- STIG mode security settings (includes faillock configuration)
- Two-factor authentication configuration
- Faillock settings for failed login attempt tracking
