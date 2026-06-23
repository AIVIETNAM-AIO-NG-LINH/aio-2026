// =====================================================================
// AIO 2026 — ai-aio (Django 5.2 + Gunicorn + Celery) CI/CD
// Jenkins chạy CHUNG EC2 (cùng docker daemon) → build & deploy LOCAL.
// KHÔNG dùng registry — build tại chỗ image aio/ai-aio:latest, deploy
// dùng thẳng image đó (up --no-build). web (Gunicorn) + worker (Celery).
//
// Deploy vào FOLDER RIÊNG /opt/aio/ai-aio, MIRROR cấu trúc docker/ của repo
// để giữ nguyên đường dẫn env_file tương đối (../.env, ./secrets.env).
//
// ENV (chỉ phần SECRET) lấy từ CREDENTIAL Jenkins kiểu "Secret file":
//   Manage Jenkins → Credentials → Secret file, ID = `env-ai-aio`
//   (nội dung = docker/secrets.env.example đã điền: DJANGO_SECRET_KEY, mật khẩu DB, API key…).
//   → pipeline copy thành /opt/aio/ai-aio/docker/secrets.env.
// CONFIG (không nhạy cảm) lấy từ repo: .env.example → /opt/aio/ai-aio/.env
//   (prod override bằng compose environment: DJANGO_DEBUG=False…).
//
// Yêu cầu: data-aio đã up (aio-net + DB/Redis/OpenSearch/Postgres/Neo4j).
// =====================================================================
pipeline {
  agent any
  options {
    timeout(time: 1, unit: 'HOURS')
  }
  environment {
    IMAGE   = 'aio/ai-aio:latest'
    APP_DIR = '/opt/aio/ai-aio'
    // Secret file → biến giữ ĐƯỜNG DẪN file tạm chứa nội dung secrets.env.
    SECRETS_FILE = credentials('env-ai-aio')
  }

  stages {
    stage('Build main') {
      when { branch 'main' }
      steps {
        echo 'Building ai-aio (prod Gunicorn + Celery)'
        sh '''#!/usr/bin/env bash
        set -e
        docker build -f docker/Dockerfile -t ${IMAGE} .
        '''
      }
    }
    stage('Deploy main') {
      when { branch 'main' }
      steps {
        // Sync compose + env vào deploy folder (mirror docker/).
        // config ← .env.example (repo); secret ← credential; cùng host nên cp local.
        sh '''#!/usr/bin/env bash
        set -e
        mkdir -p ${APP_DIR}/docker
        cp docker/docker-compose.prod.yml ${APP_DIR}/docker/docker-compose.prod.yml
        cp .env.example                   ${APP_DIR}/.env
        cp ${SECRETS_FILE}                ${APP_DIR}/docker/secrets.env
        chmod 600 ${APP_DIR}/docker/secrets.env

        cd ${APP_DIR}
        docker compose -f docker/docker-compose.prod.yml up -d --no-build
        # Reload gateway để cắt sang IP container mới NGAY (khỏi chờ TTL resolver).
        docker exec nginx-aio nginx -s reload 2>/dev/null || true
        '''
      }
    }
  }
}
