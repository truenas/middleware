<%def name="opts(share)">
</%def>
V4: /
% for share in dispatcher.call_sync("shares.query", [("type", "=", "nfs")]):
${dispatcher.call_sync('volumes.resolve_path', share['target'])}    ${opts(share)}
% endfor