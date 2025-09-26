<%
    import ipaddress
    import os

    from middlewared.logger import NGINX_LOG_PATH

    # Let's ensure that /var/log/nginx directory exists
    os.makedirs(NGINX_LOG_PATH, exist_ok=True)

    # The error log should be a real file owned by nginx
    fix_error_file = False
    nginx_error_log = os.path.join(NGINX_LOG_PATH, 'error.log')
    try:
        fix_error_file = os.path.islink(nginx_error_log)
    except FileNotFoundError:
        fix_error_file = True

    if fix_error_file:
        try:
            os.remove(nginx_error_log)
        except Exception:
            pass

        with open(nginx_error_log, 'w') as f:
            pass

        # Match owner and permissions to access.log: ['www-data','adm']
        nginx_uid = middleware.call_sync('user.get_builtin_user_id', 'www-data')
        nginx_gid = middleware.call_sync('group.get_builtin_group_id', 'adm')
        os.chown(nginx_error_log, nginx_uid, nginx_gid)
        os.chmod(nginx_error_log, 0o640)


    general_settings = middleware.call_sync('system.general.config')
    cert = general_settings['ui_certificate']
    dhparams_file = middleware.call_sync('certificate.dhparam')
    x_frame_options = '' if general_settings['ui_x_frame_options'] == 'ALLOW_ALL' else general_settings['ui_x_frame_options']

    ip_list = []
    for ip in general_settings['ui_address']:
        ip_list.append(ip)

    for ip in general_settings['ui_v6address']:
        ip_list.append(f'[{ip}]')

    wg_config = middleware.call_sync('datastore.config', 'system.truecommand')
    if wg_config['wg_address']:
        ip_list.append(ipaddress.ip_network(wg_config['wg_address'], False).network_address)

    # Let's verify that required SSL support in the backend is complete by middlewared
    if not cert or middleware.call_sync('certificate.cert_services_validation', cert['id'], 'nginx.certificate', False):
        ssl_configuration = False
        middleware.call_sync('alert.oneshot_create', 'WebUiCertificateSetupFailed', None)
    else:
        ssl_configuration = True
        middleware.call_sync('alert.oneshot_delete', 'WebUiCertificateSetupFailed', None)

    system_version = middleware.call_sync('system.version')

    # Check if FIPS mode is enabled
    fips_enabled = middleware.call_sync('system.security.info.fips_enabled')

    # HSTS max-age calculation (730 days = 63072000 seconds)
    max_age = 63072000 if general_settings['ui_httpsredirect'] else 0

    if not any(i in general_settings['ui_httpsprotocols'] for i in ('TLSv1', 'TLSv1.1')):
        disabled_ciphers = ':!SHA1:!SHA256:!SHA384'
    else:
        disabled_ciphers = ''
    display_device_path = middleware.call_sync('vm.get_vm_display_nginx_route')
    display_devices = middleware.call_sync('vm.device.query', [['attributes.dtype', '=', 'DISPLAY']])

    tn_connect_config = middleware.call_sync('tn_connect.config')
    has_tn_connect = tn_connect_config['certificate'] is not None
    try:
        tnc_basename = middleware.call_sync('tn_connect.hostname.basename_from_cert')
        tnc_cert = middleware.call_sync('certificate.get_instance', tn_connect_config['certificate']) if tn_connect_config['certificate'] else None
    except Exception:
        # This should not happen but better safe then sorry as we don't want to disrupt nginx configuration
        tnc_basename = tnc_cert = None
        middleware.logger.exception('Failed to retrieve TNC certificate information')

    servers = []
    if tnc_cert and tnc_basename:
        servers.append({
            'name': tnc_basename,
            'cert': tnc_cert,
            'default_server': False,
            })

    servers.append({
        'name': 'localhost',
        'cert': cert if ssl_configuration else None,
        'default_server': True,
    })
    current_api_version = middleware.api_versions[-1].version
%>
#
#    TrueNAS nginx configuration file
#
load_module modules/ngx_http_uploadprogress_module.so;
user www-data www-data;
worker_processes  1;

events {
    worker_connections  1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;
    # We need this because TNC domain exceeds 64
    server_names_hash_bucket_size 128;

    # Types to enable gzip compression on
    gzip_types
        text/plain
        text/css
        text/js
        text/xml
        text/javascript
        application/javascript
        application/x-javascript
        application/json
        application/xml
        application/rss+xml
        image/svg+xml;

    # reserve 1MB under the name 'proxied' to track uploads
    upload_progress proxied 1m;

    sendfile        on;
    #tcp_nopush     on;
    client_max_body_size 1000m;

    #keepalive_timeout  0;
    keepalive_timeout  65;

    # Disable tokens for security (#23684)
    server_tokens off;

% if fips_enabled:
    # Hide server information in error pages
    # NOTE: This is a DoDin requirement, so don't remove
    proxy_hide_header X-Powered-By;
    proxy_hide_header Server;

% endif
    gzip  on;

% if fips_enabled:
    # Disable gzip for responses with cookies (BREACH attack mitigation)
    # NOTE: will be controlled per-response based on Set-Cookie header
    gzip_vary on;
    gzip_proxied any;
    gzip_disable "msie6";

% endif
    access_log /var/log/nginx/access.log combined buffer=32k flush=5s;
    error_log /var/log/nginx/error.log;

    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }

    map $http_origin $allow_origin {
        ~^https://truenas.connect.(dev.|staging.)?ixsystems.net$ $http_origin;
        default "";
    }

% if fips_enabled:
    # Map to detect if response has Set-Cookie header (for disabling gzip)
    map $sent_http_set_cookie $no_gzip_cookie {
        ~.+ "1";
        default "0";
    }

% endif
% for server in servers:
    server {
        server_name  ${server['name']};
% if server['cert']:
    % for ip in ip_list:
        listen                 ${ip}:${general_settings['ui_httpsport']} ${'default_server' if server['default_server'] else ''} ssl http2;
    % endfor

        ssl_certificate        "${server['cert']['certificate_path']}";
        ssl_certificate_key    "${server['cert']['privatekey_path']}";
        ssl_dhparam "${dhparams_file}";
        ssl_session_timeout    120m;
        ssl_session_cache      shared:ssl:16m;
        ssl_protocols ${' '.join(general_settings['ui_httpsprotocols'])};
        ssl_prefer_server_ciphers on;
        ssl_ciphers EECDH+ECDSA+AESGCM:EECDH+aRSA+AESGCM:EECDH+ECDSA${"" if disabled_ciphers else "+SHA256"}:EDH+aRSA:EECDH:!RC4:!aNULL:!eNULL:!LOW:!3DES:!MD5:!EXP:!PSK:!SRP:!DSS${disabled_ciphers};

        ## If oscsp stapling is a must in cert extensions, we should make sure nginx respects that
        ## and handles clients accordingly.
        % if 'Tlsfeature' in server['cert']['extensions']:
        ssl_stapling on;
        ssl_stapling_verify on;
        % endif
        #resolver ;
        #ssl_trusted_certificate ;
% endif
% if not general_settings['ui_httpsredirect'] or not server['cert']:
    % for ip in ip_list:
        listen       ${ip}:${general_settings['ui_port']};
    % endfor
% endif
% if general_settings['ui_allowlist']:
    % for ip in general_settings['ui_allowlist']:
        allow ${ip};
    % endfor
        deny all;
% endif
<%def name="security_headers(indent=8)">
<% spaces = ' ' * indent %>
${spaces}# Security Headers
${spaces}add_header Strict-Transport-Security "max-age=${max_age}; includeSubDomains; preload" always;
${spaces}add_header X-Content-Type-Options "nosniff" always;
${spaces}add_header X-XSS-Protection "1; mode=block" always;
${spaces}add_header Permissions-Policy "geolocation=(),midi=(),sync-xhr=(),microphone=(),camera=(),magnetometer=(),gyroscope=(),fullscreen=(self),payment=()" always;
${spaces}add_header Referrer-Policy "strict-origin" always;
% if x_frame_options:
${spaces}add_header X-Frame-Options "${x_frame_options}" always;
% endif
</%def>
<%def name="security_headers_enhanced(indent=8)">
<% spaces = ' ' * indent %>
${spaces}# NOTE: These are, generaly, good practice but they
${spaces}# are also here for DoDin requirements so do not remove.
${spaces}proxy_cookie_path / "/; Secure; HttpOnly; SameSite=Strict";
${spaces}proxy_cookie_flags ~ secure httponly;
${spaces}# Disable gzip for responses with cookies (BREACH attack mitigation)
${spaces}gzip off;
</%def>
        ${security_headers()}
        location / {
            allow all;
            rewrite ^.* $scheme://$http_host/ui/ redirect;
        }
% for device in display_devices:
        location ${display_device_path}/${device['id']} {
    % if ":" in device['attributes']['bind']:
            proxy_pass http://[${device['attributes']['bind']}]:${device['attributes']['web_port']}/;
    % else:
            proxy_pass http://${device['attributes']['bind']}:${device['attributes']['web_port']}/;
    % endif
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header X-Https $https;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
        }
% endfor
        location /progress {
            # report uploads tracked in the 'proxied' zone
            report_uploads proxied;
        }

        location /api {
            allow all;  # This is handled by `Middleware.ws_can_access` because if we return HTTP 403, browser security
                        # won't allow us to understand that connection error was due to client IP not being allowlisted.
            proxy_pass http://127.0.0.1:6000/api;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header X-Https $https;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
% if fips_enabled:
            ${security_headers_enhanced(indent=12)}
% endif
        }

        location ~ ^/api/docs/?$ {
            rewrite .* /api/docs/current redirect;
        }

        location /api/docs {
            alias /usr/share/middlewared/docs;
            add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
            expires epoch;
        }

        location /api/docs/current {
            alias /usr/share/middlewared/docs/${current_api_version};
            add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
            expires epoch;
        }

        location @index {
            add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
            expires epoch;
            ${security_headers(indent=12)}
            root /usr/share/truenas/webui;
            try_files /index.html =404;
        }

        location = /ui/ {
            allow all;
            add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0" always;
            add_header Clear-Site-Data '"cache"' always;
            add_header Etag "${system_version}";
            ${security_headers(indent=12)}
            expires epoch;
            root /usr/share/truenas/webui;
            try_files /index.html =404;
        }

        location = /ui/sw.js {
            allow all;

            # `allow`/`deny` are not allowed in `if` blocks so we'll have to make that check in the middleware itself.
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Https $https;

            add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0" always;
            add_header Clear-Site-Data '"cache"' always;
            add_header Etag "${system_version}";
            ${security_headers(indent=12)}
            expires epoch;

            alias /usr/share/truenas/webui;
            try_files $uri $uri/ @index;
        }

        location = /ui/index.html {
            allow all;

            # `allow`/`deny` are not allowed in `if` blocks so we'll have to make that check in the middleware itself.
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Https $https;

            add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0" always;
            add_header Clear-Site-Data '"cache"' always;
            add_header Etag "${system_version}";
            ${security_headers(indent=12)}
            expires epoch;

            alias /usr/share/truenas/webui;
            try_files $uri $uri/ @index;
        }

        location /ui {
            allow all;

            # `allow`/`deny` are not allowed in `if` blocks so we'll have to make that check in the middleware itself.
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Https $https;

            add_header Cache-Control "must-revalidate";
            add_header Etag "${system_version}";
            ${security_headers(indent=12)}

            alias /usr/share/truenas/webui;
            try_files $uri $uri/ @index;
        }

        location /websocket {
            allow all;  # This is handled by `Middleware.ws_can_access` because if we return HTTP 403, browser security
                        # won't allow us to understand that connection error was due to client IP not being allowlisted.
            proxy_pass http://127.0.0.1:6000/websocket;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header X-Https $https;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
% if fips_enabled:
            ${security_headers_enhanced(indent=12)}
% endif
        }

        location /websocket/shell {
            allow all;  # This is handled by `Middleware.ws_can_access` because if we return HTTP 403, browser security
                        # won't allow us to understand that connection error was due to client IP not being allowlisted.
            proxy_pass http://127.0.0.1:6000/_shell;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header X-Https $https;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_send_timeout 7d;
            proxy_read_timeout 7d;
% if fips_enabled:
            ${security_headers_enhanced(indent=12)}
% endif
        }

        location /api/v2.0 {
	    # do not add the path to proxy_pass because of automatic url decoding
	    # e.g. /api/v2.0/pool/dataset/id/tank%2Ffoo/ would become
	    #      /api/v2.0/pool/dataset/id/tank/foo/
            proxy_pass http://127.0.0.1:6000;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header X-Https $https;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Server-Port $server_port;
            proxy_set_header X-Scheme $Scheme;
% if fips_enabled:
            ${security_headers_enhanced(indent=12)}
% endif
        }

        location /_download {
% if has_tn_connect:
            # Allow all internal origins.
            add_header Access-Control-Allow-Origin $allow_origin always;
            add_header Access-Control-Allow-Headers "*" always;
% endif
            proxy_pass http://127.0.0.1:6000;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header X-Https $https;
            proxy_read_timeout 10m;
% if fips_enabled:
            ${security_headers_enhanced(indent=12)}
% endif
        }

        location /_upload {
            # Allow uploads of any size. Its middlewared job to handle size.
            client_max_body_size 0;
            proxy_pass http://127.0.0.1:6000;
            # make sure nginx does not buffer the upload and pass directly to middlewared
            proxy_request_buffering off;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header X-Https $https;
% if fips_enabled:
            ${security_headers_enhanced(indent=12)}
% endif
        }

        location /_plugins {
            proxy_pass http://127.0.0.1:6000/_plugins;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header X-Https $https;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $remote_addr;
% if fips_enabled:
            ${security_headers_enhanced(indent=12)}
% endif
        }
    }
% endfor

% if general_settings['ui_httpsredirect'] and ssl_configuration:
    server {
    % for ip in ip_list:
        listen    ${ip}:${general_settings['ui_port']};
    % endfor
        server_name localhost;
        return 307 https://$host:${general_settings['ui_httpsport']}$request_uri;
    }

% endif
}
