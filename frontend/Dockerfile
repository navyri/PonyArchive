# PonyArchive — frontend (React + Vite + TypeScript)
#
#   docker build -t ponyarchive-frontend ./frontend
#
# VITE_API_URL vacío (por defecto) = el navegador llama a rutas relativas (/api, /health)
# y nginx las reenvía al backend (sin CORS en producción). Ver nginx.conf.
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# --- imagen final: solo el build estático servido por nginx ---
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
