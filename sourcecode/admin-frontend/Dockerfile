FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_ADMIN_API_URL
ENV VITE_ADMIN_API_URL=${VITE_ADMIN_API_URL}

ARG VITE_TENANT_NAME
ENV VITE_TENANT_NAME=${VITE_TENANT_NAME}

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
