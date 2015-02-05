<%def name="opts(share)">
</%def>
V4: /
% for share in dispatcher.call_sync("shares.nfs.query"):
${share['path']}    ${opts(share)}      ${' '.join(share['hosts'])}
% endfor