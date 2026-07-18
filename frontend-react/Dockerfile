# Dockerfile frontend SitasiAI — build React (Vite) lalu sajikan via nginx.
# Stage 1: build bundle statis
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: nginx serve + reverse-proxy /api (lihat nginx.conf)
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
