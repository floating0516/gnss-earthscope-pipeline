# GNSS EarthScope GA Pipeline

English | [中文](#中文说明)

This repository contains a curated GNSS earthquake-processing workflow for USGS earthquake events, EarthScope-style processing utilities, and Geoscience Australia (GA) high-rate GNSS data.

The public repository intentionally keeps only source code, workflow scripts, tests, and selected README figures. Large local products such as downloaded observations, SQLite databases, workflow runs, normalized exports, and bulk figures are excluded by `.gitignore`.

## Example outputs

The full `data/`, `runs/`, `exports/`, and bulk `figure/` directories are local pipeline products and are not committed. The selected figures below are copied under `docs/images/` only for README display.

### Global station/event coverage

![Global GNSS station/event map](docs/images/world_map.png)

### Event with the most normalized stations

Petrolia, California, 2021-12-20 (`nc73666231`) has the largest normalized station count in this workspace: 96 stations.

![Petrolia station map](docs/images/petrolia-20211220-california_station_map.png)

![Petrolia waveform record section](docs/images/petrolia-20211220-california_record_section.png)

## What is included

```text
gnss-earthscope-ga-pipeline/
├── README.md
├── environment.yml
├── pyproject.toml
├── requirements-web.txt
├── scripts/
│   ├── build_ga_au_database.py
│   ├── update_ga_event_highrate_availability.py
│   ├── run_ga_batch_workflow.sh
│   ├── run_ga_event_1hz_pride_workflow.sh
│   ├── normalize_ga_pride_kin_event.py
│   └── compute_kin_quality.py
├── src/
│   ├── gnss_eq/
│   └── gnss_eqdata/
├── tests/
└── tools/
    ├── ga_downloader/
    └── pride_processor/
```

## What is not included

The following paths are local data or generated outputs and are ignored:

```text
data/
runs/
exports/
figure/
incoming_plotting_origina/
```

Only the curated images in `docs/images/` are tracked.

## Setup

Python package metadata is in `pyproject.toml`; the package requires Python 3.10 or newer.

With conda:

```bash
conda env create -f environment.yml
conda activate gnss-earthscope-pipeline
pip install -e .[web]
```

Web-only dependencies are also listed in `requirements-web.txt`.

External runtime tools are not vendored in this repository. Depending on the workflow, the local machine should provide tools such as `curl`, `jq`, `timeout`, `CRX2RNX`, and `pdp3`.

## Main GA workflow scripts

Build or update the GA event/station database:

```bash
python scripts/build_ga_au_database.py --help
python scripts/update_ga_event_highrate_availability.py --help
```

Run GA event workflows:

```bash
scripts/run_ga_event_1hz_pride_workflow.sh --help
scripts/run_ga_batch_workflow.sh --help
```

Normalize PRIDE KIN outputs:

```bash
python scripts/normalize_ga_pride_kin_event.py --help
```

Compute KIN quality summaries:

```bash
python scripts/compute_kin_quality.py --help
```

## Dashboard

The package includes a small FastAPI dashboard under `src/gnss_eq/web.py` with static assets in `src/gnss_eq/static/`.

```bash
gnss-eq dashboard --host 127.0.0.1 --port 8765
```

Start it with `--allow-workflow-run` only when you intentionally want the dashboard to launch local workflows.

## Tests

```bash
python -m unittest discover tests
```

---

# 中文说明

[English](#gnss-earthscope-ga-pipeline) | 中文

本仓库是一个精简后的 GNSS 地震处理流程仓库，面向 USGS 地震事件、EarthScope 风格的处理工具，以及 Geoscience Australia (GA) 高频 GNSS 数据流程。

公开仓库只保留源码、工作流脚本、测试和 README 中展示用的少量图片。大型本地数据产品不会上传，包括下载的观测文件、SQLite 数据库、运行目录、标准化导出结果和批量生成图片。

## 示例输出

完整的 `data/`、`runs/`、`exports/` 和批量 `figure/` 目录都是本地 pipeline 产物，已被 `.gitignore` 排除。下面这些图片是专门复制到 `docs/images/` 中用于 README 展示的精选图片。

### 全球台站/事件分布图

![全球 GNSS 台站/事件地图](docs/images/world_map.png)

### 台站数量最多的事件

Petrolia, California，2021-12-20，事件编号 `nc73666231`，是当前工作区中 normalized station 数量最多的事件，共 96 个台站。

![Petrolia 台站地图](docs/images/petrolia-20211220-california_station_map.png)

![Petrolia 波形剖面图](docs/images/petrolia-20211220-california_record_section.png)

## 仓库包含的内容

```text
gnss-earthscope-ga-pipeline/
├── README.md
├── environment.yml
├── pyproject.toml
├── requirements-web.txt
├── scripts/
│   ├── build_ga_au_database.py
│   ├── update_ga_event_highrate_availability.py
│   ├── run_ga_batch_workflow.sh
│   ├── run_ga_event_1hz_pride_workflow.sh
│   ├── normalize_ga_pride_kin_event.py
│   └── compute_kin_quality.py
├── src/
│   ├── gnss_eq/
│   └── gnss_eqdata/
├── tests/
└── tools/
    ├── ga_downloader/
    └── pride_processor/
```

## 不上传的内容

以下路径是本地数据或自动生成结果，已被忽略：

```text
data/
runs/
exports/
figure/
incoming_plotting_origina/
```

只有 `docs/images/` 中用于 README 展示的精选图片会被 git 跟踪。

## 环境安装

Python 包配置在 `pyproject.toml` 中，要求 Python 3.10 或更新版本。

使用 conda：

```bash
conda env create -f environment.yml
conda activate gnss-earthscope-pipeline
pip install -e .[web]
```

Web 相关依赖也单独列在 `requirements-web.txt` 中。

外部运行依赖不会打包进本仓库。根据具体流程，本地机器需要安装 `curl`、`jq`、`timeout`、`CRX2RNX`、`pdp3` 等工具。

## 主要 GA 工作流脚本

构建或更新 GA 事件/台站数据库：

```bash
python scripts/build_ga_au_database.py --help
python scripts/update_ga_event_highrate_availability.py --help
```

运行 GA 事件工作流：

```bash
scripts/run_ga_event_1hz_pride_workflow.sh --help
scripts/run_ga_batch_workflow.sh --help
```

标准化 PRIDE KIN 输出：

```bash
python scripts/normalize_ga_pride_kin_event.py --help
```

计算 KIN 质量摘要：

```bash
python scripts/compute_kin_quality.py --help
```

## Dashboard

仓库包含一个简单的 FastAPI dashboard，后端在 `src/gnss_eq/web.py`，静态资源在 `src/gnss_eq/static/`。

```bash
gnss-eq dashboard --host 127.0.0.1 --port 8765
```

只有在明确希望 dashboard 启动本地工作流时，才使用 `--allow-workflow-run`。

## 测试

```bash
python -m unittest discover tests
```
