# etc_files Directory

This directory contains template and script files used by the `etc` plugin to generate system configuration files in
`/etc/`. The plugin manages configuration file generation, change detection, and proper file permissions.

## File Types

Files in this directory must be either:

1. **Mako templates** (`.mako` extension) - Preferred for most use cases
2. **Python scripts** (`.py` extension) - Used when complex logic or system operations are required

### Mako Templates

Mako templates use templating syntax to generate configuration files. Templates have access to:

- `middleware` - The middleware instance for making API calls
- `service` - The EtcService instance
- `FileShouldNotExist` - Exception class to signal that a file should be removed
- `render_ctx` - Dictionary containing pre-fetched API call results (see below)

Example:
```mako
<%
    config = middleware.call_sync('some.config')
%>
Setting=${config['value']}
```

### Python Scripts

Python scripts must define a `render()` function with one of these signatures:

```python
def render(service, middleware):
    """For entries without a render context"""
    return content  # bytes or str

def render(service, middleware, render_ctx):
    """For entries with a render context"""
    return content  # bytes or str
```

The function can be synchronous or async (`async def`).

**Important**: Python scripts should return the file contents as `bytes` or `str` so the etc plugin can properly track
changes using `write_if_changed()`. Scripts that write files directly (returning `None`) bypass change detection.

To signal that a file should not exist:
```python
from middlewared.plugins.etc import FileShouldNotExist
raise FileShouldNotExist
```

## Render Context

The `render_ctx` is a dictionary of pre-fetched API call results passed to templates and scripts. It is defined in the
group configuration in `etc.py`.

### Configuration

Groups in `etc.py` can specify a `ctx` tuple of `CtxMethod` instances to pre-fetch data:

```python
'groupname': EtcGroup(
    ctx=(
        CtxMethod(method='system.security.config'),
        CtxMethod(method='user.query', args=[[['local', '=', True]]]),
    ),
    entries=(...),
)
```

### Structure

The render_ctx dictionary contains:
- **Key**: Method name (e.g., `'system.security.config'`)
  - If `ctx_prefix` is specified, key becomes `'prefix.method'` (e.g., `'tcp.nvmet.port.transport_address_choices'`)
- **Value**: Result of calling the middleware method with specified args

### Usage in Templates

```mako
% if render_ctx['failover.licensed']:
    Licensed features enabled
% endif
```

### Usage in Python Scripts

```python
def render(service, middleware, render_ctx):
    users = render_ctx['user.query']
    security = render_ctx['system.security.config']

    # Generate configuration content
    return content.encode()
```

## File Registration

Files must be registered in the `GROUPS` dictionary in `src/middlewared/middlewared/plugins/etc.py` as
`EtcEntry` instances inside an `EtcGroup`. `EtcEntry` fields:

- `renderer_type` - `RendererType.MAKO` or `RendererType.PY`
- `path` - Output path written as `/etc/<path>` (leading `local/` is stripped); also the source
  template path under `etc_files/` unless `local_path` overrides it
- `local_path` - Overrides the source template lookup path under `etc_files/` (optional)
- `mode` - Octal permission bits (optional, default: `0o644`)
- `owner`/`group` - Builtin username/group name for file ownership (optional, default: root:root)
- `checkpoint` - `Checkpoint` enum value controlling when the entry is rendered
  (optional, default: `Checkpoint.INITIAL`); `None` means only rendered outside checkpoint calls

Example:
```python
'groupname': EtcGroup(entries=(
    EtcEntry(renderer_type=RendererType.MAKO, path='config.conf', mode=0o600),
    EtcEntry(renderer_type=RendererType.PY, path='setup_script'),
))
```
