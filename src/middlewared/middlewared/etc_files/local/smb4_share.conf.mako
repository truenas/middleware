#
# SMB.CONF(5)		The configuration file for the Samba suite 
# $FreeBSD$
#
<%
        import os
        import logging
        logger = logging.getLogger(__name__)

        def get_db_config():
            db = {}
            db['globals'] = middleware.call_sync('sharing.smb.get_global_params', None)
            db['truenas_conf'] = {'smb_ha_mode': 'STANDALONE', "failover_status": "DEFAULT"}
            db['truenas_conf']['smb_ha_mode'] = middleware.call_sync('smb.get_smb_ha_mode')
            if db['truenas_conf']['smb_ha_mode'] != 'STANDALONE':
                db['truenas_conf']['failover_status'] = middleware.call_sync('failover.status')

            db['cifs'] = middleware.call_sync('smb.config')
            db['shares'] = middleware.call_sync('sharing.smb.query', [('enabled', '=', True)])

            return db

        def make_homedir(homedir_path=None):
            """
            This creates the path to the ['homes'] share if it does not exist. This is of
            particular relevance in an AD environment where the DOMAIN directory must be
            created in order for users to connect to their homes share. The actual user
            home directory will be automatically created by pam_mkhomedir.
            """
            ret = True
            if not os.access(homedir_path, os.F_OK):
                try:
                    os.mkdir(homedir_path) 
                except Exception as e:
                    logger.debug(f"Failed to create home directory {homedir_path}: ({e})") 
                    ret = False
            return ret

        def parse_db_config(db):
            pc = {}
            for share in db['shares']:
                """
                Special behavior is needed for [homes]:
                We append %U (authenticated username) to the share path
                for non-AD environments, and %D/%U for AD environments.
                This prevents users from being able to access the each
                others home directories. %D is required for AD to prevent
                collisions between AD users and local users or users in
                trusted domains.
                """
                if share["locked"]:
                    middleware.logger.debug(
                        "Skipping generation of %r share as the underlying resource is locked", share["name"]
                    )
                    middleware.call_sync('sharing.smb.generate_locked_alert', share['id'])
                    continue
                if share["home"]:
                    share["name"] = "homes" 

                pc[share["name"]] = {}
                pc[share["name"]].update(middleware.call_sync('sharing.smb.share_to_smbconf', share, db['globals']))

                if share["home"] and db['globals']['ad_enabled']:
                    base_homedir = f"{share['path']}/{db['cifs']['workgroup']}"
                    if not pc[share["name"]].get('ixnas:zfs_auto_home_dir'):
                        make_homedir(base_homedir)
                elif is_home_share:
                    pc[share["name"]].update({"path": f'{share["path"]}/%U'})

            return pc

        try:
            if middleware.call_sync('cache.get', 'SMB_REG_INITIALIZED') is True:
                middleware.call_sync('sharing.smb.sync_registry')
                return
        except KeyError:
            pass

        db = get_db_config()
        parsed_conf = {}
        parsed_conf = parse_db_config(db)
%>

% if db['truenas_conf']['failover_status'] != "BACKUP":
% for share_name, share in parsed_conf.items():
[${share_name}]
    % for param, value in share.items():
      % if type(value) == list:
        ${param} = ${' '.join(value)}
      % else:
        ${param} = ${value}
      % endif
    % endfor

% endfor
% endif
