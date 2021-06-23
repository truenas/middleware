<%
    import contextlib
    import ipaddress
    import os

    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import dh
    from cryptography.hazmat.primitives import serialization

    from middlewared.utils import osc

    # Let's ensure that /var/log/nginx directory exists
    if not os.path.exists('/var/log/nginx'):
        os.makedirs('/var/log/nginx')

    if osc.IS_LINUX:
        with contextlib.suppress(OSError):
            os.unlink('/var/log/nginx/error.log')

        # nginx unconditionally opens this file and never closes, preventing us from unmounting system dataset
        os.symlink('/dev/null', '/var/log/nginx/error.log')

    general_settings = middleware.call_sync('system.general.config')
    cert = general_settings['ui_certificate']
    dhparams_file = middleware.call_sync('certificate.dhparam')

    # We can't afford nginx not running due to `bind(): Can't assign requested address` so we check that listen
    # addresses exist.
    ip_in_use = [ip['address'] for ip in middleware.call_sync('interface.ip_in_use', {'ipv6_link_local': False})]

    middleware.call_sync('alert.oneshot_delete', 'WebUiBindAddressV2', 'IPv4')
    if general_settings['ui_address'] == ['0.0.0.0']:
        ip4_list = general_settings['ui_address']
    else:
        ip4_list = [ip for ip in general_settings['ui_address'] if ip in ip_in_use]
        ip4_absent = [ip for ip in general_settings['ui_address'] if ip not in ip_in_use]
        if ip4_absent:
            ip4_list = ['0.0.0.0']
            middleware.call_sync('alert.oneshot_create', 'WebUiBindAddressV2', {
                'family': 'IPv4',
                'addresses': ', '.join(ip4_absent),
                'wildcard': '0.0.0.0',
            })

    middleware.call_sync('alert.oneshot_delete', 'WebUiBindAddressV2', 'IPv6')
    if general_settings['ui_v6address'] == ['::']:
        ip6_list = general_settings['ui_v6address']
    else:
        ip6_list = [ip for ip in general_settings['ui_v6address'] if ip in ip_in_use]
        ip6_absent = [ip for ip in general_settings['ui_v6address'] if ip not in ip_in_use]
        if ip6_absent:
            ip6_list = ['::']
            middleware.call_sync('alert.oneshot_create', 'WebUiBindAddressV2', {
                'family': 'IPv6',
                'addresses': ', '.join(ip6_absent),
                'wildcard': '::',
            })
    ip6_list = [f'[{ip}]' for ip in ip6_list]

    wg_config = middleware.call_sync('datastore.config', 'system.truecommand')
    if middleware.call_sync('truecommand.connected')['connected'] and wg_config['wg_address']:
        ip4_list.append(ipaddress.ip_network(wg_config['wg_address'], False).network_address)

    ip_list = ip4_list + ip6_list

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
%>
#
#    FreeNAS nginx configuration file
#

% if IS_FREEBSD:
    load_module /usr/local/libexec/nginx/ngx_http_uploadprogress_module.so;
% endif
% if IS_LINUX:
    load_module modules/ngx_http_uploadprogress_module.so;
% endif

% if IS_FREEBSD:
    user www www;
% endif
% if IS_LINUX:
    user www-data www-data;
% endif
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
    #upload_store /var/tmp/firmware;
    client_body_temp_path /var/tmp/firmware;

    error_log syslog:server=unix:/var/run/log,nohostname;
    access_log syslog:server=unix:/var/run/log,nohostname;

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
        add_header Strict-Transport-Security max-age=${31536000 if general_settings['ui_httpsredirect'] else 0};

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

        # Security Headers
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1";

        location / {
            rewrite ^.* $scheme://$http_host/ui/ redirect;
        }

        location /progress {
            # report uploads tracked in the 'proxied' zone
            report_uploads proxied;
        }

        location /api/docs {
            proxy_pass http://127.0.0.1:6000/api/docs;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Scheme $scheme;
            proxy_set_header X-Script-Name /api/docs;
        }

        location /api/docs/restful/static {
% if IS_FREEBSD:
            alias /usr/local/www/swagger-ui/node_modules/swagger-ui-dist;
% else:
            alias /usr/local/share/swagger-ui-dist;
% endif
        }

        location /ui {
            if ( $request_method ~ ^POST$ ) {
                proxy_pass http://127.0.0.1:6000;
            }
            try_files $uri $uri/ /index.html =404;
% if IS_FREEBSD:
            alias /usr/local/www/webui;
% endif
% if IS_LINUX:
            alias /usr/share/truenas/webui;
% endif
            add_header Cache-Control "must-revalidate";
            add_header Etag "${system_version}";
        }

        location /websocket {
            proxy_pass http://127.0.0.1:6000/websocket;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }

        location /websocket/shell {
            proxy_pass http://127.0.0.1:6000/_shell;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
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
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $remote_addr;
        }

        location /_download {
            proxy_pass http://127.0.0.1:6000;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
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
        }

        location /images {
            alias /var/db/system/webui/images;
        }

        location /_plugins {
            proxy_pass http://127.0.0.1:6000/_plugins;
            proxy_http_version 1.1;
            proxy_set_header X-Real-Remote-Addr $remote_addr;
            proxy_set_header X-Real-Remote-Port $remote_port;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $remote_addr;
        }

        #error_page  404              /404.html;

        # redirect server error pages to the static page /50x.html
        #
        error_page   500 502 503 504  /50x.html;
        location = /50x.html {
            root   /usr/local/www/nginx-dist;
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
