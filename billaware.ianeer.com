server {
    listen 80;
    server_name billaware.ianeer.com;

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name billaware.ianeer.com;

    ssl_certificate     /etc/letsencrypt/live/billaware.ianeer.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/billaware.ianeer.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:9000;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 60;
        proxy_connect_timeout 60;
        proxy_send_timeout 60;
    }
}
