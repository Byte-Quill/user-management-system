FROM node:22-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .

# VITE_API_URL is OPTIONAL. Leave it unset when the SPA is served from the
# same origin as the API (e.g. the docker-compose nginx proxy) — the client
# then uses the relative "/api" base automatically.
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# Templated: the nginx entrypoint renders ${XFP} from the XFP env var into
# /etc/nginx/conf.d/default.conf at container start.
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 80
