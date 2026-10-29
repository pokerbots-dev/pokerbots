FROM python:3.13-slim
COPY cli /app/cli
RUN pip install --no-cache-dir /app/cli
COPY runner /app/runner
WORKDIR /app/runner
EXPOSE 8080
CMD ["python", "server.py"]
