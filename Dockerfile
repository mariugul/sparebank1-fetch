FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY sb1/ ./sb1/

RUN pip install --no-cache-dir "click>=8.1.0" "httpx>=0.27.0" "keyring>=25.0.0" "hatchling" \
    && pip install --no-cache-dir -e .

ENV SB1_CLIENT_ID=""
ENV SB1_CLIENT_SECRET=""

ENTRYPOINT ["sb1"]
CMD ["--help"]
