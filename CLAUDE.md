# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is the TrueNAS middleware repository, which contains the core daemon that powers the TrueNAS storage operating system. The middleware is an async Python-based WebSocket API server with a distributed plugin architecture.

## Build and Development Commands

### Building and Installing Middleware

```bash
# Full rebuild, install, and service restart (run from src/middlewared/)
make reinstall

# Individual steps:
make stop_service      # Stop the middlewared service
make build_deb         # Build Debian package
make install           # Install built package
make migrate           # Run database migrations
make start_service     # Restart middlewared service

# For container builds (no systemd)
make reinstall_container
```

### Running Tests

**Integration/API Tests** (requires connection to TrueNAS instance):
```bash
# Run all API tests
./tests/runtest.py --ip <IP> --password <PASSWORD> --interface <INTERFACE>

# Run specific test directory
./tests/runtest.py --ip <IP> --password <PASSWORD> --interface <INTERFACE> --test_dir api2
./tests/runtest.py --ip <IP> --password <PASSWORD> --interface <INTERFACE> --test_dir sharing_protocols

# Run specific test file
./tests/runtest.py --ip <IP> --password <PASSWORD> --interface <INTERFACE> --test test_smb.py

# Run multiple specific tests
./tests/runtest.py --ip <IP> --password <PASSWORD> --interface <INTERFACE> --tests test_lock.py,test_mail.py
```

**Unit Tests**:
```bash
python3 tests/run_unit_tests.py
```

**Development Mode** (live debugging with console output):
```bash
systemctl stop middlewared
middlewared --log-handler=console --debug-level DEBUG
```

### Test Dependencies

Install test dependencies on Debian-based systems:
```bash
apt install python3-pip samba smbclient sshpass snmp libiscsi-dev
cd tests && pip3 install -r requirements.txt
```

## Architecture Overview

### Core Components

**Middleware Daemon** (`src/middlewared/middlewared/main.py`):
- Main entry point is the `Middleware` class
- Async Python application built on aiohttp for WebSocket API
- Manages plugin loading, service lifecycle, and job queuing
- Handles API versioning and method routing

**Plugin System** (`src/middlewared/middlewared/plugins/`):
- 70+ plugin modules organized as either:
  - Single-file plugins: `account.py`, `smb.py`, `nfs.py`, etc.
  - Multi-directory plugins: `account_/`, `smb_/`, `nfs_/`, etc. (for complex functionality)
- Each plugin exports one or more Service classes
- Services are automatically discovered and registered by the middleware daemon

**Service Types**:
- `Service`: Base service class for general functionality
- `ConfigService`: Configuration-only operations (no CRUD)
- `CRUDService`: Full Create/Read/Update/Delete with datastore integration
- `CompoundService`: Combines multiple implementations for same namespace
- `SharingService`: Base for file sharing protocols (SMB, NFS, iSCSI, etc.)
- `SystemServiceService`: For system-wide daemon management

### API Method Declaration

Methods are declared with the `@api_method` decorator:

```python
@api_method(
    InputArgsType,      # Pydantic-style input validation model
    OutputReturnType,   # Pydantic-style output validation model
    roles=['ROLE_NAME'],  # Required RBAC roles
    audit='Action description',  # Audit logging
    pass_app=True,      # Optional: inject app context
)
async def do_create(self, app, data):
    # Implementation
    pass
```

**API Model Field Descriptions**:
- Every field in API models (`Args`, `Result`, `Entry` classes) **must** have a description via `Field(description=...)`.
- This is enforced by `test_api_docstrings` in the unit test suite.
- Description can be formatted with Markdown.

**Method Docstrings**:
- Every public API method (decorated with `@api_method`) **must** have a docstring.
- The docstring is a description of the method, formatted with reStructuredText (RST).
- Do **not** use Google- or NumPy-style docstrings (no `Args:`/`Returns:`/`Parameters` sections).
- Do **not** document parameters or return values in the method docstring; those descriptions belong only in the API models (see **API Model Field Descriptions** above).
- Every mention of another API method (or the method itself) **must** be a method reference, e.g. ``:method:`core.bulk` ``. The docs preprocessor expands this to the full ``:doc:`core.bulk <api_methods_core.bulk>` `` cross-reference at build time.
- If the description includes example code, it **must** be JSON-RPC (as passed by the API client), not Python.

**API Versioning**:
- Multiple API versions maintained in parallel (`src/middlewared/middlewared/api/v*/`)
- Legacy methods wrapped with `LegacyAPIMethod`

### Data Persistence

**Database System**:
- SQLite-based with SQLAlchemy ORM
- Models inherit from `middlewared.sqlalchemy.Model`
- Database migrations managed via Alembic (`src/middlewared/middlewared/alembic/`)
- Custom column types: `EncryptedText`, `JSON`, `MultiSelectField`, `DateTime`, `Time`

**Datastore Access**:
- Via `self.middleware.call('datastore.query', 'table', filters, options)`
- CRUD: `datastore.create()`, `datastore.update()`, `datastore.delete()`
- Supports filtering and complex queries

### Job System

**Async Job Execution** (`middlewared/job.py`):
- Methods decorated with `@job` become async background jobs
- Job states: WAITING, RUNNING, SUCCESS, FAILED, ABORTED
- Job logs stored in `/var/log/jobs/`
- Progress callback support for long-running operations

**Calling Other Services**:
```python
# From within a service:
result = await self.middleware.call('service.method', arg1, arg2)

# Calling with job support:
job_id = await self.middleware.call('service.long_running_method', arg1)
```

### Authorization & Authentication

**RBAC System** (`middlewared/role.py`):
- 50+ role types for granular access control
- Role prefixes: `READONLY_ADMIN`, `SHARING_*`, `SERVICE_*`, `ACCOUNT_*`, etc.
- Each API method specifies required roles
- Session-based authentication via WebSocket

**Common Patterns**:
- Services log via `self.logger` (automatically provided)
- Error handling via `CallError` and `ValidationError` exceptions
- Database queries abstracted through datastore service
- All I/O operations should be async (`async def`, `await`)

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `src/middlewared/middlewared/` | Main middleware package |
| `src/middlewared/middlewared/plugins/` | Service plugins (core business logic) |
| `src/middlewared/middlewared/api/` | API versioning and type definitions |
| `src/middlewared/middlewared/service/` | Service base classes and decorators |
| `src/middlewared/middlewared/utils/` | Shared utilities |
| `src/middlewared/middlewared/alert/` | Alert/notification system |
| `src/middlewared/middlewared/etc_files/` | Config file templates (Mako and Python scripts) |
| `src/middlewared/middlewared/alembic/` | Database migrations |
| `tests/` | Integration and API test suites |
| `tests/api2/` | Main API tests (200+ tests) |
| `tests/sharing_protocols/` | SMB, NFS, iSCSI, Fibre Channel, NVMe-oF tests |
| `tests/directory_services/` | AD, LDAP, FreeIPA, SSH tests |
| `tests/unit/` | Internal middleware unit tests |

## Development Workflow

### Adding a New API Endpoint

1. **Create or modify a service plugin** in `src/middlewared/middlewared/plugins/`
2. **Define input/output types** using Pydantic-style models in the service
3. **Add the method** with `@api_method` decorator and appropriate roles
4. **Implement the logic** using async/await
5. **Rebuild and install**: `make -C src/middlewared reinstall`
6. **Test the endpoint** using WebSocket API or integration tests

### Making Database Schema Changes

1. **Update the model** in the service plugin
2. **Create an Alembic migration**: `alembic revision -m "description"`
3. **Edit the migration** in `src/middlewared/middlewared/alembic/versions/`
4. **Run migration**: `make -C src/middlewared migrate`

### Writing Integration Tests

Tests use pytest and WebSocket client from `middlewared.test.integration.utils`:

```python
from middlewared.test.integration.utils import call, ssh

def test_example():
    # Call API method
    result = call('service.method', arg1, arg2)

    # Execute SSH command on test system
    output = ssh('ls -la /mnt/pool')

    # Assert results
    assert result['status'] == 'SUCCESS'
```

Common test patterns:
- Use `@pytest.fixture(scope="module")` for test setup/teardown
- Use `call()` for API method invocation
- Use `ssh()` for direct command execution on test system
- Use context managers for resource cleanup

## Python Standards

- **Python 3.11+** required
- Use modern type hints: `dict`, `list`, `set` instead of `typing.Dict`, `typing.List`, `typing.Set` (PEP-585)
- Do not use `select.select`; use `poll` instead
- All async code should use proper `async`/`await` patterns
- Follow existing code style in the repository
- **Atomic file writes**: Use `atomic_write` from `middlewared.utils.io` when writing system config files, security-sensitive files (SSH keys, credentials), or files that other processes may be reading concurrently. It provides atomic replacement with symlink race protection. Use standard `open()` for regular application data, logs, or temporary files.

## Logging Guidelines

Log **problems and state changes, not routine success** — absence of error messages means things worked. Use `self.logger`.

**Levels:**
- **ERROR** — operation failures, unexpected exceptions (always `exc_info=True`), service state problems, data inconsistencies.
- **WARNING** — recoverable/degraded conditions, non-critical config issues, failed non-critical cleanup, unexpected-but-handled data.
- **INFO** — significant state changes and milestones (pool imports, service starts, setup completion).
- **DEBUG** — flow through complex multi-step operations, significant code-path entry/exit, race-condition workarounds.

**Do NOT log:** routine reads/queries/`get_instance`, datastore lookups and config retrieval, successful routine CRUD, internal helper calls, data transforms, cache hits, or anything sensitive (credentials, keys, passwords). For input validation raise `ValidationError`; for permission/operational failures raise `CallError` — don't log instead of raising.

**Conventions:**
- Include a resource identifier in every message; use the `'resource: description'` format.
- Pass `exc_info=True` on all exception logs to capture the stack trace.
- Log an error once — don't re-log the same failure at multiple levels as it propagates.

```python
except Exception:
    self.logger.error('%s: failed to perform operation', resource_name, exc_info=True)
    raise
```

## Important Notes

- **Service Access**: Always call other services via `self.middleware.call('service.method', ...)`, never import and instantiate directly.
- **Database Access**: Use the datastore service abstraction, not direct SQL queries.
- **Error Handling**: Use `CallError` for operational/runtime failures (system state, resource busy, I/O errors). Use `ValidationError` only when the **caller's input** is the problem (invalid argument value, nonexistent entity referenced by an argument, incompatible options). If the input is valid but the system can't perform the operation, that's a `CallError`, not a `ValidationError`.
- **Logging**: Use `self.logger` in services for consistent logging (see Logging Guidelines above).
