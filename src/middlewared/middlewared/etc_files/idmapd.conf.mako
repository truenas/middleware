<%
    config = render_ctx["nfs.config"]
%>

[General]
Verbosity = 0
% if config['v4_domain']:
Domain = ${config['v4_domain']}
% endif

[Mapping]
Nobody-User = nobody
Nobody-Group = nogroup

[Translation]
Method = nsswitch
