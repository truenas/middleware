user www
worker_process 1

events {
    worker_connections 1024;
}

http {
    include mime.types;
    default_type application/octet-stream;

    sendfile on;
    client_max_body_size 500m;
    keepalive_timeout  65;

    server {
        listen 0.0.0.0:80;
        server_name localhost;

        location / {
            proxy_pass http://localhost:3000/;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        location /socket {
            proxy_pass http://localhost:5000/socket;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}