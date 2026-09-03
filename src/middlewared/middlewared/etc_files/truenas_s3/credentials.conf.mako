<%
    # One section per access key. Only an ENABLED key renders enabled: a
    # disabled row needs neither a secret nor a resolvable user, which is
    # what lets a key whose account is gone, or whose secret was lost,
    # stay in the file without refusing the load.
    keys = render_ctx["s3.render_data"]["accesskeys"]
%>\
% for key in keys:
[credential "${key["access_key"]}"]
% if key["secret"]:
secret_key = ${key["secret"]}
% endif
% if key["username"]:
user = ${key["username"]}
% endif
enabled = ${"true" if key["status"] == "ENABLED" else "false"}

% endfor
