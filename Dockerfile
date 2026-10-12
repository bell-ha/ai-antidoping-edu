# 데모·시범 공용 이미지. 프로세스 1개가 API와 화면을 함께 서빙한다 (D18, §10).

# 1) 프론트 빌드
# 재현성: 베이스 이미지는 패치 버전까지, pip 의존성은 requirements.lock으로 고정 (§10)
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
# 의존성만 설치한다. 패키지로 설치하면 코드가 site-packages로 옮겨져 data/ 경로(config.ROOT)가 틀어진다.
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY data /app/data
COPY knowledge /app/knowledge
COPY --from=web /src/frontend/dist /app/frontend/dist
# 약물 DB: 원천 JSON에서 빌드한다(원천 sha256을 meta에 기록 → 시범 모드 시작 검사가 같은 해시를 확인)
RUN python -m app.drug_db

RUN useradd --system --uid 10001 app && mkdir -p /app/data/llm_cache && chown -R app /app/data/llm_cache
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"
# 워커는 1개로 유지한다. 로그인 실패 기록과 @cache가 프로세스마다 따로라 워커를 늘리면 제한이 느슨해진다.
# 프록시 뒤에서는 FORWARDED_ALLOW_IPS 환경변수(uvicorn이 읽음)에 프록시 IP를 넣는다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
