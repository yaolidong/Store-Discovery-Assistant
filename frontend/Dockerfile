# Stage 1: Build the Vue.js application
FROM node:18-alpine AS build-stage

# Set the working directory
WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock, pnpm-lock.yaml)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Serve the application with Nginx
FROM nginx:alpine

# Copy the build output from the build stage to the Nginx html directory
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copy the custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
