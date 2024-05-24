<%
    from middlewared.utils.directoryservices.constants import DSType
    from middlewared.plugins.directoryservices_.all import get_enabled_ds

    enabled_ds = get_enabled_ds()
%>
#
# nsswitch.conf(5) - name service switch configuration file
#

% if enabled_ds is None:
group: files
passwd: files
netgroup: files
% elif enabled_ds.ds_type is DSType.AD:
group: files winbind
passwd: files winbind
netgroup: files
% else:
group: files sss
passwd: files sss
netgroup: files sss
% endif
hosts: files dns
networks: files
shells: files
services: files
protocols: files
rpc: files
sudoers: files
