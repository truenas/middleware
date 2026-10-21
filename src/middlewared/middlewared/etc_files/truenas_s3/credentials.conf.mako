<%
    # One section per access key. Only an ENABLED key with a secret
    # renders enabled. The S3 service refuses an enabled key without a
    # secret or a user. expires_at is a Unix timestamp.
    keys = render_ctx["s3.render_data"].accesskeys
%>\
% for key in keys:
[credential "${key.entry.access_key}"]
% if key.secret:
secret_key = ${key.secret}
% endif
% if key.entry.username:
user = ${key.entry.username}
% endif
enabled = ${"true" if key.entry.status == "ENABLED" and key.secret else "false"}
% if key.entry.expires_at:
expires_at = ${int(key.entry.expires_at.timestamp())}
% endif
% if key.entry.manage_buckets:
manage_buckets = true
% endif

% endfor
