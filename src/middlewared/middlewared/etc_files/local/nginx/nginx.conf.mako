<%
    import contextlib
    import ipaddress
    import os

    # Let's ensure that /var/log/nginx directory exists
    if not os.path.exists('/var/log/nginx'):
        os.makedirs('/var/log/nginx')

    with contextlib.suppress(OSError):
        os.unlink('/var/log/nginx/error.log')

    # nginx unconditionally opens this file and never closes, preventing us from unmounting system dataset
    os.symlink('/dev/null', '/var/log/nginx/error.log')

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

    if not any(i in general_settings['ui_httpsprotocols'] for i in ('TLSv1', 'TLSv1.1')):
        disabled_ciphers = ':!SHA1:!SHA256:!SHA384'
    else:
        disabled_ciphers = ''
    display_device_path = middleware.call_sync('vm.get_vm_display_nginx_route')
    display_devices = middleware.call_sync('vm.device.query', [['attributes.dtype', '=', 'DISPLAY']])

    has_tn_connect = middleware.call_sync('tn_connect.config')['certificate'] is not None

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

    gzip  on;
    access_log off;
    error_log syslog:server=unix:/dev/log,nohostname;

    # Rate limiting zones for TrueNAS WebShare
    # Connection limit zones
    limit_conn_zone $binary_remote_addr zone=webshare_conn_ip:10m;
    limit_conn_zone $server_name$request_uri zone=webshare_conn_downloads:10m;

    # Request rate limit zone (600 requests per minute = 10 req/s)
    limit_req_zone $binary_remote_addr zone=webshare_req:10m rate=600r/m;

    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }

    map $http_origin $allow_origin {
        ~^https://truenas.connect.(dev.|staging.)?ixsystems.net$ $http_origin;
        default "";
    }

    server {
        server_name  localhost;
% if ssl_configuration:
    % for ip in ip_list:
        listen                 ${ip}:${general_settings['ui_httpsport']} default_server ssl http2;
    % endfor

        ssl_certificate        "${cert['certificate_path']}";
        ssl_certificate_key    "${cert['privatekey_path']}";
        ssl_dhparam "${dhparams_file}";

        ssl_session_timeout    120m;
        ssl_session_cache      shared:ssl:16m;

        ssl_protocols ${' '.join(general_settings['ui_httpsprotocols'])};
        ssl_prefer_server_ciphers on;
        ssl_ciphers EECDH+ECDSA+AESGCM:EECDH+aRSA+AESGCM:EECDH+ECDSA${"" if disabled_ciphers else "+SHA256"}:EDH+aRSA:EECDH:!RC4:!aNULL:!eNULL:!LOW:!3DES:!MD5:!EXP:!PSK:!SRP:!DSS${disabled_ciphers};

        ## If oscsp stapling is a must in cert extensions, we should make sure nginx respects that
        ## and handles clients accordingly.
        % if 'Tlsfeature' in cert['extensions']:
        ssl_stapling on;
        ssl_stapling_verify on;
        % endif
        #resolver ;
        #ssl_trusted_certificate ;
% endif

% if not general_settings['ui_httpsredirect'] or not ssl_configuration:
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

<%def name="security_headers()">
        # Security Headers
        add_header Strict-Transport-Security "max-age=${63072000 if general_settings['ui_httpsredirect'] else 0}; includeSubDomains; preload" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Permissions-Policy "geolocation=(),midi=(),sync-xhr=(),microphone=(),camera=(),magnetometer=(),gyroscope=(),fullscreen=(self),payment=()" always;
        add_header Referrer-Policy "strict-origin" always;
% if x_frame_options:
        add_header X-Frame-Options "${x_frame_options}" always;
% endif
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
        }

        location ~ ^/api/docs/?$ {
            rewrite .* /api/docs/current redirect;
        }

        location /api/docs {
            alias /usr/share/middlewared/docs;
            add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
            add_header Expires 0;
        }

        location /api/docs/current {
            alias /usr/share/middlewared/docs/${current_api_version};
            add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
            add_header Expires 0;
        }

        location @index {
            add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
            add_header Expires 0;
            ${security_headers()}

            root /usr/share/truenas/webui;
            try_files /index.html =404;
        }

        location = /ui/ {
            allow all;

            add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
            add_header Expires 0;
            ${security_headers()}

            root /usr/share/truenas/webui;
            try_files /index.html =404;
        }

        location /ui {
            allow all;

            # `allow`/`deny` are not allowed in `if` blocks so we'll have to make that check in the middleware itself.
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Https $https;

            add_header Cache-Control "must-revalidate";
            add_header Etag "${system_version}";
            ${security_headers()}

            alias /usr/share/truenas/webui;
            try_files $uri $uri/ @index;
        }

        # Handle all download API requests - file and directory downloads
        location ~ ^/webshare/download/([^/]+)/api/ {
           # Rewrite to remove /webshare prefix before passing to backend
           rewrite ^/webshare(.*)$ $1 break;

           proxy_pass http://unix:/var/run/webshare/auth.sock;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;

           # Important for file downloads
           proxy_buffering off;
           proxy_read_timeout 3600s;
           proxy_send_timeout 3600s;
           client_max_body_size 0;
        }

        # Handle upload file requests directly - MUST come BEFORE the general /webshare/ location
        location ~ ^/webshare/upload/([^/]+)/file$ {
            # Rewrite to remove /webshare prefix before passing to backend
            rewrite ^/webshare(.*)$ $1 break;

            proxy_pass http://unix:/var/run/webshare/auth.sock;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            client_max_body_size 0;
            proxy_request_buffering off;
            proxy_connect_timeout 3600s;  # Keep for initial connection
            proxy_read_timeout 86400s;    # 24 hours - let uploads run for very long
            proxy_send_timeout 86400s;    # 24 hours - let uploads run for very long
            client_body_timeout 86400s;   # 24 hours - let uploads run for very long
            send_timeout 86400s;          # 24 hours - let uploads run for very long

            # Keepalive and TCP settings to prevent connection drops
            proxy_set_header Connection "";
            proxy_buffering off;
            proxy_http_version 1.1;
            tcp_nodelay on;               # Send data immediately
            tcp_nopush off;               # Don't buffer TCP packets
        }

        location /webshare/ {
            allow all;

            # Enforce HTTPS only
            if ($https != "on") {
                return 301 https://$host:${general_settings['ui_httpsport']}$request_uri;
            }

            # `allow`/`deny` are not allowed in `if` blocks so we'll have to make that check in the middleware itself.
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Https $https;

            add_header Cache-Control "must-revalidate";
            add_header Etag "${system_version}";

            # Security Headers
            add_header Strict-Transport-Security "max-age=0; includeSubDomains; preload" always;
            add_header X-Content-Type-Options "nosniff" always;
            add_header X-XSS-Protection "1; mode=block" always;
            add_header Permissions-Policy "geolocation=(),midi=(),sync-xhr=(),microphone=(),camera=(),magnetometer=(),gyroscope=(),fullscreen=(self),payment=()" always;
            add_header Referrer-Policy "strict-origin" always;
            add_header X-Frame-Options "SAMEORIGIN" always;

            alias /usr/share/truenas-webshare/truenas-webshare-auth-ui/browser/;
            try_files $uri $uri/ /webshare/index.html;
        }

        location /webshare {
            allow all;

            # Enforce HTTPS only
            if ($https != "on") {
                return 301 https://$host:${general_settings['ui_httpsport']}$request_uri;
            }

            # `allow`/`deny` are not allowed in `if` blocks so we'll have to make that check in the middleware itself.
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Https $https;

            add_header Cache-Control "must-revalidate";
            add_header Etag "${system_version}";

            # Security Headers
            add_header Strict-Transport-Security "max-age=0; includeSubDomains; preload" always;
            add_header X-Content-Type-Options "nosniff" always;
            add_header X-XSS-Protection "1; mode=block" always;
            add_header Permissions-Policy "geolocation=(),midi=(),sync-xhr=(),microphone=(),camera=(),magnetometer=(),gyroscope=(),fullscreen=(self),payment=()" always;
            add_header Referrer-Policy "strict-origin" always;
            add_header X-Frame-Options "SAMEORIGIN" always;

            alias /usr/share/truenas-webshare/truenas-webshare-auth-ui/browser/;
            try_files $uri $uri/ /webshare/index.html;
        }

        location = /webshare/browser/ {
            allow all;

            # Enforce HTTPS only
            if ($https != "on") {
                return 301 https://$host:${general_settings['ui_httpsport']}$request_uri;
            }

            add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
            add_header Pragma "no-cache";
            add_header Expires "0";
            expires -1;

            # Security Headers
            add_header Strict-Transport-Security "max-age=0; includeSubDomains; preload" always;
            add_header X-Content-Type-Options "nosniff" always;
            add_header X-XSS-Protection "1; mode=block" always;
            add_header Permissions-Policy "geolocation=(),midi=(),sync-xhr=(),microphone=(),camera=(),magnetometer=(),gyroscope=(),fullscreen=(self),payment=()" always;
            add_header Referrer-Policy "strict-origin" always;
            add_header X-Frame-Options "SAMEORIGIN" always;

            root /usr/share/truenas-webshare/truenas-file-manager-ui/browser;
            try_files /index.html =404;
        }

        location /webshare/browser {
            allow all;

            # Enforce HTTPS only
            if ($https != "on") {
                return 301 https://$host:${general_settings['ui_httpsport']}$request_uri;
            }

            # `allow`/`deny` are not allowed in `if` blocks so we'll have to make that check in the middleware itself.
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Https $https;

            add_header Cache-Control "must-revalidate";
            add_header Etag "${system_version}";

            # Security Headers
            add_header Strict-Transport-Security "max-age=0; includeSubDomains; preload" always;
            add_header X-Content-Type-Options "nosniff" always;
            add_header X-XSS-Protection "1; mode=block" always;
            add_header Permissions-Policy "geolocation=(),midi=(),sync-xhr=(),microphone=(),camera=(),magnetometer=(),gyroscope=(),fullscreen=(self),payment=()" always;
            add_header Referrer-Policy "strict-origin" always;
            add_header X-Frame-Options "SAMEORIGIN" always;

            alias /usr/share/truenas-webshare/truenas-file-manager-ui/browser;
            try_files $uri $uri/ @index;
        }

        # Proxy WebSocket connections to the auth service
        location /webshare/ws {
            # Enforce HTTPS only
            if ($https != "on") {
                return 301 https://$host:${general_settings['ui_httpsport']}$request_uri;
            }

            proxy_pass http://unix:/var/run/webshare/auth.sock:/ws;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header X-Https $https;

            # WebSocket timeouts
            proxy_read_timeout 86400;
            proxy_connect_timeout 86400;
            proxy_send_timeout 86400;
        }

        # API endpoints - strip /webshare prefix when proxying
        location ~ ^/webshare/api/(.*)$ {
            proxy_pass http://unix:/var/run/webshare/auth.sock:/api/$1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Cookie $http_cookie;  # Forward cookies for httpOnly auth

            # Allow large file uploads for upload API endpoints
            client_max_body_size 0;
            proxy_request_buffering off;

            # Timeout settings for large uploads via API
            proxy_connect_timeout 3600s;  # Keep for initial connection
            proxy_read_timeout 86400s;    # 24 hours - let uploads run for very long
            proxy_send_timeout 86400s;    # 24 hours - let uploads run for very long
            client_body_timeout 86400s;   # 24 hours - let uploads run for very long
            send_timeout 86400s;          # 24 hours - let uploads run for very long

            # Keepalive and TCP settings
            proxy_set_header Connection "";
            proxy_buffering off;
            proxy_http_version 1.1;
            tcp_nodelay on;
            tcp_nopush off;
        }

        # Health check endpoint
        location /webshare/health {
            # Enforce HTTPS only
            if ($https != "on") {
                return 301 https://$host:${general_settings['ui_httpsport']}$request_uri;
            }

            proxy_pass http://unix:/var/run/webshare/auth.sock:/health;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Include all webshare session configurations
        include /etc/nginx/webshare-includes/*.conf;

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
        }

        location /_plugins {
            proxy_pass http://127.0.0.1:6000/_plugins;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header X-Https $https;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $remote_addr;
        }
    }
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
