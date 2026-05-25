# Build the React application
FROM node:lts-alpine AS build-stage

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Pass VITE_* at build time, e.g.:
# docker build --build-arg VITE_API_URL=https://your-backend ...
ARG VITE_API_URL
ARG VITE_DONATE_URL
ARG VITE_SOCIAL_YOUTUBE
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_DONATE_URL=$VITE_DONATE_URL
ENV VITE_SOCIAL_YOUTUBE=$VITE_SOCIAL_YOUTUBE

RUN npm run build

# Serve static files on Cloud Run's PORT (default 8080)
FROM nginx:stable-alpine AS production-stage

RUN apk add --no-cache gettext \
    && rm -f /etc/nginx/conf.d/default.conf

COPY nginx/default.conf.template /etc/nginx/conf.d/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

COPY --from=build-stage /app/dist /usr/share/nginx/html

ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]
