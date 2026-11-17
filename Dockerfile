# Quokka lab app. Ollama is not in this image: it runs in its own container
# (the "ollama" service in docker-compose.yml), reached at http://ollama:11434.
#
# Base image pinned by the digest of the multi-arch index (python:3.12-slim,
# Python 3.12.16, Debian trixie, built 2026-10-28). Checked on 2026-10-30 with
# `docker buildx imagetools inspect python:3.12-slim`: the index contains
#   linux/amd64     sha256:1148dbb014615300fa7e713b2f94f550c0d1c69780c0805f84f093ceee34dd0b
#   linux/arm64/v8  sha256:b224e2fe306f9d303251ada22961635e5b52a69c0414a0050611be31c59f5f5b
# so the same line works on Intel/AMD laptops and Apple Silicon.
FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

# Print logs right away (Quokka's console), and don't write .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Run as an ordinary user, not root (least privilege).
RUN useradd --create-home --uid 10001 quokka
# Saved progress lives in /data. A new named volume mounted here copies this
# folder's owner, so the quokka user can write to it.
RUN mkdir /data && chown 10001:10001 /data
ENV QUOKKA_DATA_DIR=/data
WORKDIR /app

# Standard library only: nothing to pip install. Only the app itself goes in.
COPY quokka/ ./quokka/

USER quokka
# Ctrl+C / `docker compose down` sends SIGINT, which Python turns into a clean exit
# (Python running as PID 1 would otherwise ignore the default SIGTERM).
STOPSIGNAL SIGINT
EXPOSE 9080 9081 9082 9083
CMD ["python", "-m", "quokka"]
