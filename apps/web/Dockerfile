# Imagem do frontend (Next.js). node:22 = linha LTS ativa (Next 16 exige >=20.9).
FROM node:22-alpine

WORKDIR /app

# Instala deps a partir do lockfile (camada cacheável).
COPY package.json package-lock.json ./
RUN npm ci

# Código da aplicação.
COPY . .

# A URL da API é embutida no bundle em build time (variável NEXT_PUBLIC_*).
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
