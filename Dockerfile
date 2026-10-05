FROM node:22-bookworm-slim AS frontend
WORKDIR /app
COPY package*.json ./
RUN npm ci --ignore-scripts
COPY frontend frontend
COPY static static
COPY scripts scripts
ARG SITE_URL=""
ENV SITE_URL=$SITE_URL PUBLIC_BASE_PATH=/
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home candidaro
COPY backend backend
COPY prompts prompts
COPY --from=frontend /app/frontend frontend
COPY --from=frontend /app/static static
COPY --from=frontend /app/_site _site
RUN mkdir -p data/uploads && chown -R candidaro:candidaro /app/data
USER candidaro
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
