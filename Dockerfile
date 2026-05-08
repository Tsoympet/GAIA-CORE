FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "gaia.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
