FROM nginx:1.27-alpine

# Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Static site
COPY site/ /usr/share/nginx/html/

EXPOSE 8080
