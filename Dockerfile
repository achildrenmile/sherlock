FROM python:3.12-alpine
WORKDIR /app
COPY sherlock.py server.py VERSION ./
COPY static ./static
RUN adduser -D -u 10001 sherlock
USER sherlock
ENV HOST=0.0.0.0 PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s CMD wget -qO- http://127.0.0.1:8080/hilfe >/dev/null || exit 1
CMD ["python3", "server.py"]
