# Isolated agent workspace: NEVER copy graders, mutants or reference code here.
FROM python:3.12-slim
WORKDIR /app
RUN python -m pip install --no-cache-dir pytest==9.0.2
COPY service.py /app/service.py
ENV PYTHONDONTWRITEBYTECODE=1
