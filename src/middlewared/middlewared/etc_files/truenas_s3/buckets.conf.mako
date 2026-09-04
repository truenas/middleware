<%
    # The daemon reads this file whole and one malformed value refuses the
    # entire load: keys stay lowercase, a heading name stays quoted, an enum
    # renders as the daemon's lowercase token, and a key the daemon would
    # refuse empty is omitted rather than printed empty. Every enabled
    # bucket renders, a missing dataset included: the daemon excludes a row
    # it cannot mount and answers 503 for it, where an omitted row would
    # answer NoSuchBucket.
    data = render_ctx["s3.render_data"]
    config = data.config

    def audit_value(mask):
        # ALL is the daemon's `all`; a list, empty included, is the mask
        return "all" if mask == "ALL" else ",".join(mask)
%>\
[server]
% if data.listen:
listen = ${data.listen}
% endif
## a TLS listener renders whatever pair the deployment has, a missing
## half included: the daemon refuses the load rather than serve the
## address in the clear, and that refusal is the answer the caller gets
% if data.listen_tls:
listen_tls = ${data.listen_tls}
% if data.tls_cert:
tls_cert = ${data.tls_cert}
% endif
% if data.tls_key:
tls_key = ${data.tls_key}
% endif
% endif
servers = ${config.servers}
% if config.region:
region = ${config.region}
% endif
host_id = ${data.host_id}
owner_id_seed = ${data.owner_id_seed}
log_level = ${config.log_level.lower()}
% if data.audit_licensed:
% if config.default_audit:
default_audit = ${audit_value(config.default_audit)}
% endif
default_audit_overflow = ${config.default_audit_overflow.lower()}
% endif
% for bucket in data.buckets:
<% b = bucket.entry %>\
% if b.enabled:

[bucket "${b.name}"]
dataset = ${b.dataset}
path = ${bucket.mountpoint}
owner = ${b.owner}
owner_id = ${b.owner_uid}
permissions_model = ${b.permissions_model.lower()}
versioning = ${b.versioning.lower()}
## a selection of none is the key omitted, never rendered empty; the cap
## is inert without a selection, so it rides beside one
% if b.snapshot_versions:
snapshot_versions = ${", ".join(b.snapshot_versions)}
snapshot_versions_max = ${b.snapshot_versions_max}
% endif
multipart_etag = ${b.multipart_etag.lower()}
object_lock = ${"enabled" if b.object_lock else "off"}
% if b.object_lock_default_mode:
object_lock_default_mode = ${b.object_lock_default_mode.lower()}
% endif
% if b.object_lock_default_days:
object_lock_default_days = ${b.object_lock_default_days}
% endif
% if data.audit_licensed:
## None inherits the server default by omission; an empty list is the
## empty mask, rendered so it shadows the default
% if b.audit is not None:
audit = ${audit_value(b.audit)}
% endif
% if b.audit_overflow:
audit_overflow = ${b.audit_overflow.lower()}
% endif
% endif
% endif
% endfor
