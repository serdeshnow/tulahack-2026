# Stage 1: build
FROM node:20-alpine AS builder

# ARG VITE_APP_NAME
# ARG VITE_API_URL
# ARG VITE_X_TOKEN
# ARG VITE_GITHUB_REPOSITORY_URL
# ARG VITE_ENABLE_MOCK_API
# ARG VITE_ALLOW_GUEST_ACCESS

# ENV VITE_APP_NAME=$VITE_APP_NAME
# ENV VITE_API_URL=$VITE_API_URL
# ENV VITE_X_TOKEN=$VITE_X_TOKEN
# ENV VITE_GITHUB_REPOSITORY_URL=$VITE_GITHUB_REPOSITORY_URL
# ENV VITE_ENABLE_MOCK_API=$VITE_ENABLE_MOCK_API
# ENV VITE_ALLOW_GUEST_ACCESS=$VITE_ALLOW_GUEST_ACCESS

WORKDIR /app

# Using yarn v4 with corepack
COPY package.json yarn.lock .yarnrc.yml ./
RUN corepack enable && yarn install --immutable

COPY . .
RUN yarn build

# Stage 2: runtime (static)
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf

# Vite build output
COPY --from=builder /app/build /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
