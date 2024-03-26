#
# SMB.CONF(5)		The configuration file for the Samba suite 
#

[global]
% for param, value in render_ctx['smb.generate_smb_configuration'].items():
    ${param} = ${value}
% endfor
