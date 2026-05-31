# Use a Node.js base image for building the Vue application
FROM node:lts-alpine as build-stage

# Set the working directory inside the container
WORKDIR /app

# Copy package.json and package-lock.json to install dependencies
COPY package*.json ./

# Install project dependencies
RUN npm install

# Copy the entire React application code
COPY . .

# Build the React application for production
RUN npm run build

# Use a lightweight Nginx image to serve the built application
FROM nginx:stable-alpine as production-stage

# Copy the built React application from the build stage to Nginx's html directory
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Expose port 80 for web traffic
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
