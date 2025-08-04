<%
    if middleware.call_sync('failover.is_single_master_node'):
        enabled_ds = middleware.call_sync('directoryservices.status')['type']
    else:
        enabled_ds = None

%>
#
# nsswitch.conf(5) - name service switch configuration file
#

% if enabled_ds is None:
group: files
passwd: files
netgroup: files
% elif enabled_ds == 'ACTIVEDIRECTORY':
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
