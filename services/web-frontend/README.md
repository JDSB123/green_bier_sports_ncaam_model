# Web Frontend (Static)

Static landing/status page served by nginx.

## Build and serve locally

```bash
cd services/web-frontend
docker build -t ncaam-web .
docker run --rm -p 8080:80 ncaam-web
```

Then browse to http://localhost:8080.

## Notes

- No dynamic runtime; HTML lives in `site/` and is served by nginx per `nginx.conf`.
- Update `site/index.html` and rebuild to change content.
