# Official vLLM CPU runtime; version is deliberately pinned.
FROM vllm/vllm-openai-cpu:v0.27.0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/vllm \
    HF_HOME=/models/.huggingface \
    VLLM_LOGGING_LEVEL=INFO

# The upstream CPU image contains the complete, version-matched vLLM runtime
# and its transitive dependencies. This project adds no Python runtime packages.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin vllm \
    && mkdir -p /app /models \
    && chown -R 10001:10001 /app /models /home/vllm

WORKDIR /app
COPY --chown=10001:10001 app/ /app/app/
COPY --chown=10001:10001 scripts/ /app/scripts/
COPY --chown=10001:10001 requirements.txt /app/requirements.txt
COPY --chown=10001:10001 docker-entrypoint.sh /app/docker-entrypoint.sh

RUN chmod 0555 /app/docker-entrypoint.sh \
    && python -c "import vllm; assert vllm.__version__ == '0.27.0', vllm.__version__"

USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
