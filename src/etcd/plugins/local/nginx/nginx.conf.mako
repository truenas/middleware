user www;
pid /var/run/nginx.pid;
error_log /var/log/nginx-error.log debug;

events {
    worker_connections 1024;
}

http {
    include mime.types;
    default_type application/octet-stream;

    sendfile on;
    client_max_body_size 500m;
    keepalive_timeout 65;

    server {
% if config.get("service.nginx.http.enable"):
    % for addr in config.get("service.nginx.listen"):
        listen ${addr}:${config.get("service.nginx.http.port")};
    % endfor
% endif
% if config.get("service.nginx.https.enable"):
    % for addr in config.get("service.nginx.listen"):
        listen ${addr}:${config.get("service.nginx.https.port")} default_server ssl spdy;
    % endfor

        ssl_session_timeout	120m;
	    ssl_session_cache	shared:ssl:16m;

        ssl_certificate ${config.get("service.nginx.https.ssl_cert")};
        ssl_certificate_key ${config.get("service.nginx.https.ssl_key")}
        ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
        ssl_prefer_server_ciphers on;
        ssl_ciphers EECDH+ECDSA+AESGCM:EECDH+aRSA+AESGCM:EECDH+ECDSA+SHA256:EECDH+aRSA+RC4:EDH+aRSA:EECDH:RC4:!aNULL:!eNULL:!LOW:!3DES:!MD5:!EXP:!PSK:!SRP:!DSS;
        add_header Strict-Transport-Security max-age=31536000;
% endif
        server_name localhost;

        location / {
            proxy_pass http://127.0.0.1:3000/;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        location /socket {
            proxy_pass http://127.0.0.1:5000/socket;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }

    ## Rule to remove trailing slash from the URL.
    rewrite ^/(.*)/$ /$1 permanent;
    }
}
