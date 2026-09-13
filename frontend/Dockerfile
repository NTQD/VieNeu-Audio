# Frontend that (Step 9+15 cua build order, Section 12 cua spec). Build
# context la chinh frontend/ (xem docker-compose.yml o goc repo).
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* phai co MAT LUC BUILD (Next inline chung vao bundle client,
# khong doc duoc tu env luc container chay) - truyen qua build arg, docker-
# compose.yml o goc repo set gia tri nay.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
