<%
    # Every enabled bucket's grants, then the wildcard rows. The heading
    # names the principal kind, its label and the bucket; the xid is the
    # identity the daemon matches on, so everyone carries none.
    data = render_ctx["s3.render_data"]
    rows = [
        grant
        for bucket in data.buckets
        if bucket.entry.enabled
        for grant in bucket.grants
    ] + data.global_grants
%>\
% for row in rows:
[${row.heading}]
% if row.grant.principal_type != "EVERYONE":
xid = ${row.grant.xid}
% endif
access = ${row.grant.access.lower()}

% endfor
