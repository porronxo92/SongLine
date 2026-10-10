# Web: compila apps/web con Node y entrega dist/ desde una imagen de Caddy.
# Contexto de build: raíz del repo.
FROM node:24-alpine AS build
WORKDIR /src/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /src/apps/web/dist /srv
COPY infra/Caddyfile /etc/caddy/Caddyfile
