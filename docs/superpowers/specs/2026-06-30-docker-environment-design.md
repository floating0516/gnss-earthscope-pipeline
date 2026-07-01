# Docker Environment Design

## Goal

Prepare a Docker-based runtime for this repository so the project code and data remain on the host at `/mnt/data/gnss-earthscope-pipeline`, while the container provides a reproducible Python, EarthScope CLI, and system-tool environment for running the GNSS EarthScope pipeline.

## Current State

- `external/bin/CRX2RNX` exists and is executable.
- `external/bin/pdp3` exists and is executable.
- No existing `Dockerfile`, `docker-compose.yml`, `compose.yml`, `compose.yaml`, or `.dockerignore` was present before setup, so adding Docker files did not overwrite existing container configuration.
- `docker-home/` is used as the persisted container home directory for credentials and tool state such as EarthScope CLI login.

## Selected Approach

Use a minimal Python 3.11 slim image with system dependencies installed by `apt`, install the EarthScope CLI into the image, and mount the repository and external binaries with Docker Compose. Because this host currently times out when contacting Docker Hub directly, the Dockerfile uses the equivalent official Docker Library mirror at `public.ecr.aws/docker/library/python:3.11-slim`.

This keeps the image small and avoids copying project data into the image. The repository remains editable on the host, and workflow outputs continue to be written into the normal project directories through the bind mount.

## Alternatives Considered

1. **Minimal Python image with bind mounts plus EarthScope CLI in the image** — selected. It is simple, fast to build, keeps host data in place, matches the user's requested setup, and makes `es` available before login.
2. **Do not install EarthScope CLI initially** — useful for the very first smoke test, but `gnss-eq check-env` showed `es` was the remaining missing command, so the CLI is now installed in the image.
3. **Conda-based image using `environment.yml`** — closer to local conda workflows but heavier and unnecessary for this Docker runtime pass.

## Files Added

### `Dockerfile`

- Base image: `public.ecr.aws/docker/library/python:3.11-slim`, equivalent to the official Python 3.11 slim Docker Library image but reachable from this host.
- Install required system tools used by the workflow, including `bash`, `curl`, `jq`, `gzip`, `sqlite3`, `git`, `file`, `procps`, and `openssh-client`.
- Install `earthscope-cli==1.1.2` and `earthscope-sdk==1.3.1`, matching the user's old-machine CLI version pair.
- Create a `gnss` user with UID/GID `1000:1000` for normal bind-mount file ownership.
- Set `PATH` so `/opt/external/bin` is available.
- Use `/workspace/gnss-earthscope-pipeline` as the working directory.
- Start with `bash` by default.

### `docker-compose.yml`

- Build the local image from `Dockerfile`.
- Run the service as user `1000:1000`.
- Mount the repository at `/workspace/gnss-earthscope-pipeline`.
- Mount `./external/bin` read-only at `/opt/external/bin`.
- Mount `./docker-home` at `/home/gnss`.
- Set `HOME=/home/gnss` and environment variables pointing PRIDE/local binary paths at `/opt/external/bin`.
- Put `/home/gnss/.local/bin` and `/opt/external/bin` on `PATH`.
- Run `pip install --user -e . && exec bash` through non-login `bash -c` when entering the container, so the Compose-provided `PATH` including `/opt/external/bin` is preserved.

### `.dockerignore`

- Exclude large mutable host directories such as `data/`, `runs/`, `exports/`, `figure/`, `reports/`, `external/`, and `docker-home/` from the Docker build context.
- These paths are bind-mounted at runtime instead of baked into the image.

## Validation

After creating the files:

1. Run `docker compose build`.
2. Run a non-interactive container command to verify `CRX2RNX`, `pdp3`, `es`, and `gnss-eq` are available.
3. Run `gnss-eq check-env` inside the container.

Expected result after the user logs in with `es login`: Docker, Python, local package installation, `CRX2RNX`, `pdp3`, EarthScope CLI `es`, and EarthScope auth should be available. Before login, `gnss-eq check-env` should report only EarthScope auth as missing if network reachability is otherwise available.
