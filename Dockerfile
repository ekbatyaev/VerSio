FROM ghcr.io/ggml-org/llama.cpp:server-cuda-b8746

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* && python3 -m venv /venv
ENV PATH=/venv/bin:$PATH \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/versio
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src

ENTRYPOINT ["python", "-m", "src.main"]