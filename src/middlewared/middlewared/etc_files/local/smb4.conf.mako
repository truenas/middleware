#
# SMB.CONF(5)		The configuration file for the Samba suite 
#
<%
   shares = render_ctx['smb.generate_smb_configuration'].pop('SHARES')
%>

[global]
% for param, value in render_ctx['smb.generate_smb_configuration'].items():
    ${param} = ${value}
% endfor

% for share_name, params in shares.items():
[${share_name}]
% for param, value in params.items():
    % if isinstance(value, list):
    ${param} = ${' '.join(value)}
    % else:
    ${param} = ${value}
    % endif
% endfor

% endfor
