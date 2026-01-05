FROM nginx:1.27-alpine

ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.revision=$GIT_SHA \
    org.opencontainers.image.created=$BUILD_DATE

ENV GIT_SHA=$GIT_SHA \
    BUILD_DATE=$BUILD_DATE

# Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Static site
COPY site/ /usr/share/nginx/html/

EXPOSE 8080
