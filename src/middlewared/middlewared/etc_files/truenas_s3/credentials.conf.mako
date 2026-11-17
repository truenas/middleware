<%
    # One section per access key. Only an ENABLED key with a secret
    # renders enabled: a disabled row needs neither a secret nor a
    # resolvable user, which is what lets a key whose account is gone, or
    # whose secret was lost, stay in the file without refusing the load.
    # The secrets are read apart from the keys, so a key deleted between
    # the two reads renders disabled too. expires_at, when set, is a Unix
    # timestamp.
    data = render_ctx["s3.render_data"]
%>\
% for key in data.accesskeys:
<% secret = data.secrets.get(key.access_key) %>\
[credential "${key.access_key}"]
% if secret:
secret_key = ${secret}
% endif
% if key.username:
user = ${key.username}
% endif
enabled = ${"true" if key.status == "ENABLED" and secret else "false"}
% if key.expires_at:
expires_at = ${int(key.expires_at.timestamp())}
% endif
% if key.manage_buckets:
manage_buckets = true
% endif

% endfor
