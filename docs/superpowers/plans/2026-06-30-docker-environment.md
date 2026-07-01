# Docker Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and validate a Docker Compose runtime for the GNSS EarthScope pipeline while keeping project code and data on the host.

**Architecture:** Use a minimal Python 3.11 slim image with required system packages and pinned EarthScope CLI dependencies. The Dockerfile uses `public.ecr.aws/docker/library/python:3.11-slim`, which is the official Docker Library Python slim image mirrored through AWS Public ECR because this host times out against Docker Hub directly. Docker Compose bind-mounts the repository, external binaries, and a persisted container home directory so workflow data and credentials remain outside the image.

**Tech Stack:** Docker, Docker Compose, Python 3.11, Debian slim packages, EarthScope CLI 1.1.2, EarthScope SDK 1.3.1, editable Python package install via `pip install --user -e .`.

## Global Constraints

- Project root remains `/mnt/data/gnss-earthscope-pipeline` on the host.
- Container project path is `/workspace/gnss-earthscope-pipeline`.
- External binaries are mounted read-only from `./external/bin` to `/opt/external/bin`.
- Persisted container home is mounted from `./docker-home` to `/home/gnss`.
- EarthScope CLI is installed in the image as `earthscope-cli==1.1.2` with `earthscope-sdk==1.3.1`, matching the old-machine version pair.
- Compose runs as UID/GID `1000:1000` so files created in bind mounts are owned by the host user.
- Do not overwrite existing Docker config files without reading them first; initial inspection found none.

---

## File Structure

- Create `Dockerfile`: defines the local Python runtime image, system dependencies, EarthScope CLI dependencies, and non-root `gnss` user.
- Create `docker-compose.yml`: defines the `gnss-eq` service, bind mounts, environment variables, user mapping, and entry command.
- Create `.dockerignore`: prevents large mutable host directories from being sent as Docker build context.
- Create/keep `docker-home/`: persisted home directory for credentials and EarthScope CLI login state.
- No source package files are modified.

---

### Task 1: Add Docker runtime files

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Ensure directory exists: `docker-home/`

**Interfaces:**
- Consumes: Host files `external/bin/CRX2RNX` and `external/bin/pdp3`.
- Produces: A Docker Compose service named `gnss-eq` that can run commands in `/workspace/gnss-earthscope-pipeline` with `/opt/external/bin` and `/home/gnss/.local/bin` on PATH.

- [x] **Step 1: Confirm external binaries are present and executable**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import stat
root = Path('/mnt/data/gnss-earthscope-pipeline')
for name in ['CRX2RNX', 'pdp3']:
    path = root / 'external' / 'bin' / name
    if not path.exists():
        raise SystemExit(f'missing {path}')
    if not (path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
        raise SystemExit(f'not executable {path}')
    print(f'ok {path}')
PY
```

Expected: prints `ok` lines for both binaries.

- [x] **Step 2: Create `docker-home/`**

Run:

```bash
mkdir -p /mnt/data/gnss-earthscope-pipeline/docker-home
```

Expected: command exits successfully.

- [x] **Step 3: Write `Dockerfile`**

Create `/mnt/data/gnss-earthscope-pipeline/Dockerfile` with:

```dockerfile
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
```

- [x] **Step 4: Write `docker-compose.yml`**

Create `/mnt/data/gnss-earthscope-pipeline/docker-compose.yml` with:

```yaml
services:
  gnss-eq:
    build:
      context: .
      dockerfile: Dockerfile
    image: gnss-earthscope-pipeline:local
    working_dir: /workspace/gnss-earthscope-pipeline
    user: "1000:1000"
    environment:
      PATH: /home/gnss/.local/bin:/opt/external/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin
      PRIDE_BIN_DIR: /opt/external/bin
      LOCAL_BIN_DIR: /opt/external/bin
      HOME: /home/gnss
    volumes:
      - .:/workspace/gnss-earthscope-pipeline
      - ./external/bin:/opt/external/bin:ro
      - ./docker-home:/home/gnss
    stdin_open: true
    tty: true
    command: bash -c "pip install --user -e . && exec bash"
```

- [x] **Step 5: Write `.dockerignore`**

Create `/mnt/data/gnss-earthscope-pipeline/.dockerignore` with:

```dockerignore
.git
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

data/
runs/
exports/
figure/
reports/
external/
docker-home/

.env
.env.*
.DS_Store
```

- [x] **Step 6: Validate Compose configuration syntax**

Run:

```bash
cd /mnt/data/gnss-earthscope-pipeline && docker compose config >/tmp/gnss-compose-config.yml
```

Expected: command exits successfully.

---

### Task 2: Build and validate the Docker environment

**Files:**
- Uses: `Dockerfile`
- Uses: `docker-compose.yml`

**Interfaces:**
- Consumes: Compose service `gnss-eq` from Task 1.
- Produces: A locally built image `gnss-earthscope-pipeline:local` and check results from inside the container.

- [ ] **Step 1: Build the Docker image**

Run:

```bash
cd /mnt/data/gnss-earthscope-pipeline && docker compose build
```

Expected: build completes successfully and creates/updates `gnss-earthscope-pipeline:local`.

- [ ] **Step 2: Verify mounted external binaries, EarthScope CLI, and editable package install**

Run:

```bash
cd /mnt/data/gnss-earthscope-pipeline && docker compose run --rm -T gnss-eq bash -c 'command -v CRX2RNX && command -v pdp3 && command -v es && es --version && pip install --user -e . && command -v gnss-eq && gnss-eq --help >/tmp/gnss-help.txt && echo OK'
```

Expected: prints paths for `CRX2RNX`, `pdp3`, `es`, and `gnss-eq`, prints `earthscope-cli/1.1.2 earthscope-sdk/1.3.1`, then prints `OK`.

- [ ] **Step 3: Run project environment check**

Run:

```bash
cd /mnt/data/gnss-earthscope-pipeline && docker compose run --rm -T gnss-eq bash -c 'pip install --user -e . >/tmp/pip-install.log && gnss-eq check-env'
```

Expected: environment report runs. Before the user logs in, missing EarthScope auth is acceptable and should be reported as remaining work.

- [ ] **Step 4: Summarize results**

Report:

```text
Docker image build: PASS or FAIL
CRX2RNX in container: PASS or FAIL
pdp3 in container: PASS or FAIL
es in container: PASS or FAIL
gnss-eq installed in container: PASS or FAIL
gnss-eq check-env: PASS or FAIL, with exact remaining missing items
```

---

## Self-Review

- Spec coverage: The plan creates the Dockerfile, Compose service, Docker ignore file, persisted Docker home, pinned EarthScope CLI, non-root runtime user, and validation commands described in the spec.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: Not applicable; this plan adds configuration files and runs shell validation commands.
