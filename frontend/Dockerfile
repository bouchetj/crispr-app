# syntax=docker/dockerfile:1.4

ARG APP_ENV=prod

FROM node:22-alpine AS base

WORKDIR /app

# Install dependencies based on lockfile for reproducible builds
COPY package*.json ./
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm ci

FROM base AS dev

ENV NODE_ENV=development

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM base AS build

ENV NODE_ENV=production

# Build the production bundle
COPY . .
RUN npm run build

FROM nginx:alpine AS prod

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

FROM ${APP_ENV}

ARG APP_ENV
ENV APP_ENV=${APP_ENV}
