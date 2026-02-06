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
| `src/middlewared/middlewared/etc_files/` | Config file templates (Mako) |
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

## Logging Guidelines

The middleware follows a philosophy of **logging problems and state changes, not routine success**. The absence of error messages indicates successful operation.

### When TO Log

**ERROR level** (`self.logger.error`):
- Operation failures that prevent functionality
- Unexpected exceptions (always use `exc_info=True`)
- Service state problems
- Critical configuration errors
- Data inconsistencies

```python
try:
    # operation
except Exception:
    self.logger.error('%s: failed to perform operation', resource_name, exc_info=True)
    raise
```

**WARNING level** (`self.logger.warning`):
- Recoverable errors or degraded functionality
- Configuration issues that don't prevent operation
- Missing or unexpected data that can be handled
- Failed cleanup operations that aren't critical
- Unexpected conditions that succeeded but shouldn't have occurred

**INFO level** (`self.logger.info`):
- Significant system state changes (pool imports, service starts)
- Major configuration changes
- Initialization/setup completion messages
- Important milestones in long-running operations

**DEBUG level** (`self.logger.debug`):
- Progress tracking through complex multi-step operations
- Entry/exit of significant code paths
- State transitions that help trace execution flow
- Race condition detection or workarounds applied

### When NOT to Log

**Do NOT log:**
- ❌ Standard read operations (`.query()`, `.get_instance()`)
- ❌ Database lookups and configuration retrieval
- ❌ Input validation (raise `ValidationError` instead)
- ❌ Permission checks (raise `CallError` instead)
- ❌ Successful routine CRUD operations
- ❌ Internal helper method calls
- ❌ Data transformation/formatting operations
- ❌ Cache lookups or simple getters/setters
- ❌ Sensitive data (credentials, keys, passwords)

### Logging Patterns

```python
# Pattern 1: Exception with context and stack trace
try:
    result = perform_operation()
except Exception:
    self.logger.error('Failed to perform operation on %r', resource_id, exc_info=True)
    raise CallError(f'Operation failed: {error}')

# Pattern 2: Warning for non-critical failures
if not expected_condition:
    self.logger.warning('%s: unexpected condition detected', resource_name)

# Pattern 3: Debug for complex operation flow
self.logger.debug('Starting multi-step operation on %r', resource_name)
# ... step 1 ...
self.logger.debug('Completed step 1, beginning step 2')
# ... step 2 ...
self.logger.debug('Operation completed successfully')

# Pattern 4: Info for significant state changes
self.logger.info('Pool %r imported successfully', pool_name)

# Pattern 5: Structured message format
self.logger.error('%s: %s', resource_identifier, description)
```

### Key Principles

1. **Context is critical**: Always include resource identifiers (pool name, share ID, etc.)
2. **Use `exc_info=True`**: For all exceptions to capture stack traces
3. **Structured format**: Use `'resource: description'` pattern consistently
4. **No success logging**: Don't log when things work as expected
5. **Log once**: Don't log the same error at multiple levels

## Important Notes

- **Service Access**: Always call other services via `self.middleware.call('service.method', ...)`, never import and instantiate directly.
- **Database Access**: Use the datastore service abstraction, not direct SQL queries.
- **Error Handling**: Use `CallError` for general errors and `ValidationError` for input validation failures.
- **Logging**: Use `self.logger` in services for consistent logging (see Logging Guidelines above).
