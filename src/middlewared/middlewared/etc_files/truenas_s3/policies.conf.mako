<%
    # Every enabled bucket's grants, then the wildcard rows. A heading
    # names the principal kind, its label (quoted, already stripped of
    # anything that would break the grammar) and the bucket; the xid is
    # the identity the daemon matches on, so everyone carries none.
    data = render_ctx["s3.render_data"]

    def heading(grant, bucket):
        kind = grant["principal_type"].lower()
        if kind == "everyone":
            return f'grant everyone "{bucket}"'
        return f'grant {kind} "{grant["label"]}" "{bucket}"'

    rows = [
        (grant, bucket["name"])
        for bucket in data["buckets"]
        if bucket["enabled"]
        for grant in bucket["grants"]
    ] + [(grant, "*") for grant in data["config"]["global_grants"]]
%>\
% for grant, bucket in rows:
[${heading(grant, bucket)}]
% if grant["principal_type"] != "EVERYONE":
xid = ${grant["xid"]}
% endif
access = ${grant["access"].lower()}

% endfor
