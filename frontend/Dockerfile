# Use a lightweight Nginx image
FROM nginx:alpine

# Copy static assets from the current directory (frontend) to Nginx default server root
# Assumes this Dockerfile is in the 'frontend' directory and 'COPY .' copies 'frontend' contents
COPY . /usr/share/nginx/html

# Add a custom Nginx configuration for Vue Router history mode
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
