# 이미지 하나 = 서버 하나. 프로세스 1개가 API와 화면을 함께 서빙한다(프론트·백엔드를 따로 배포하지 않는다).
# 더미 선수 넣기: SEED_DUMMY=1이면 시작할 때 비어 있는 DB에 넣는다. 또는 docker compose exec app python /app/scripts/seed_dummy.py

# 1) 프론트 빌드
# 재현성: 베이스 이미지는 패치 버전까지, pip 의존성은 requirements.lock으로 고정
FROM node:24.14.0-alpine AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) 서버
FROM python:3.14.7-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
# 의존성만 설치한다. 패키지로 설치하면 코드가 site-packages로 옮겨져 knowledge/ 경로(config.ROOT)가 틀어진다.
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/app ./app
COPY backend/settings ./settings
COPY scripts/seed_dummy.py scripts/create_admin.py scripts/backup_db.py /app/scripts/
COPY knowledge /app/knowledge
COPY --from=web /src/frontend/dist /app/frontend/dist
# 약물 DB: 원천 JSON에서 빌드한다(원천 sha256을 meta에 기록 → 서버가 시작할 때 원천과 다르면 다시 빌드)
RUN python -m app.drugs.drug_db

# var/는 실행 사용자와 상관없이 쓸 수 있게 한다(Cloudtype처럼 uid를 1000 등으로 바꿔 실행하는 곳이 있음)
RUN useradd --system --uid 10001 app && mkdir -p /app/var/db && chown -R app /app/var && chmod -R a+rwX /app/var
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"
# 워커는 1개로 유지한다. 로그인 실패 기록과 @cache가 프로세스마다 따로라 워커를 늘리면 제한이 느슨해진다.
# 프록시 뒤에서는 FORWARDED_ALLOW_IPS 환경변수(uvicorn이 읽음)에 프록시 IP를 넣는다.
CMD ["sh", "-c", "if [ \"$SEED_DUMMY\" = 1 ]; then python /app/scripts/seed_dummy.py || true; fi; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
