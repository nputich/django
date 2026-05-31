# Build stage
FROM node:lts-alpine AS build-stage

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ARG VITE_API_URL=https://django-backend-460809694305.us-central1.run.app
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Production stage
FROM nginx:stable-alpine AS production-stage

# SPA routing + listen on port 80 (matches Cloud Run PORT=80)
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build-stage /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
