<%
    # The daemon reads this file whole and one malformed value refuses the
    # entire load: keys stay lowercase, a heading name stays quoted, an enum
    # renders as the daemon's lowercase token, and a key the daemon would
    # refuse empty is omitted rather than printed empty. Every enabled
    # bucket renders, a missing dataset included: the daemon excludes a row
    # it cannot mount and answers 503 for it, where an omitted row would
    # answer NoSuchBucket.
    data = render_ctx["s3.render_data"]
    config = data["config"]
    audit_licensed = data["audit_licensed"]

    def audit_value(mask):
        # ALL is the daemon's `all`; a list, empty included, is the mask
        return "all" if mask == "ALL" else ",".join(mask)
%>\
[server]
% if config["listen"]:
listen = ${config["listen"]}
% endif
% if config["listen_tls"]:
listen_tls = ${config["listen_tls"]}
tls_cert = ${config["tls_cert"]}
tls_key = ${config["tls_key"]}
% endif
servers = ${config["servers"]}
% if config["region"]:
region = ${config["region"]}
% endif
host_id = ${config["host_id"]}
owner_id_seed = ${config["owner_id_seed"]}
log_level = ${config["log_level"].lower()}
% if audit_licensed:
% if config["default_audit"]:
default_audit = ${audit_value(config["default_audit"])}
% endif
default_audit_overflow = ${config["default_audit_overflow"].lower()}
% endif
% for bucket in data["buckets"]:
% if bucket["enabled"]:

[bucket "${bucket["name"]}"]
dataset = ${bucket["dataset"]}
path = ${bucket["mountpoint"]}
owner = ${bucket["owner"]}
owner_id = ${bucket["owner_uid"]}
permissions_model = ${bucket["permissions_model"].lower()}
versioning = ${bucket["versioning"].lower()}
object_lock = ${"enabled" if bucket["object_lock"] else "off"}
% if bucket["object_lock_default_mode"]:
object_lock_default_mode = ${bucket["object_lock_default_mode"].lower()}
% endif
% if bucket["object_lock_default_days"]:
object_lock_default_days = ${bucket["object_lock_default_days"]}
% endif
% if audit_licensed:
## None inherits the server default by omission; an empty list is the
## empty mask, rendered so it shadows the default
% if bucket["audit"] is not None:
audit = ${audit_value(bucket["audit"])}
% endif
% if bucket["audit_overflow"]:
audit_overflow = ${bucket["audit_overflow"].lower()}
% endif
% endif
% endif
% endfor
