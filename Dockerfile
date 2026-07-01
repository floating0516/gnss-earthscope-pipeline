FROM public.ecr.aws/docker/library/python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/external/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    coreutils \
    curl \
    jq \
    grep \
    gzip \
    sqlite3 \
    ca-certificates \
    procps \
    file \
    git \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    earthscope-cli==1.1.2 \
    earthscope-sdk==1.3.1

RUN groupadd --gid 1000 gnss \
    && useradd --uid 1000 --gid 1000 --create-home --home-dir /home/gnss --shell /bin/bash gnss

WORKDIR /workspace/gnss-earthscope-pipeline

CMD ["bash"]
