# GNSS Earthquake Pipeline

English | [中文](#中文说明)

This repository contains a generalized GNSS earthquake-processing workflow. It is designed around earthquake event catalogs, high-rate GNSS station availability, event-window downloads, PRIDE PPP-AR processing, quality checks, and normalized plotting/export products.

The workflow is not tied to one country or network. Any region can be used when an event catalog, station metadata, and high-rate GNSS data access are available. The current codebase includes a GA/Geoscience Australia adapter as one data-source implementation, but the repository is presented as a generic pipeline.

The public repository intentionally keeps only source code, workflow scripts, tests, readable event summaries, and selected README figures. Large local products such as downloaded observations, SQLite databases, workflow runs, normalized exports, and bulk figures are excluded by `.gitignore`.

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
gnss-earthquake-pipeline/
├── README.md
├── environment.yml
├── pyproject.toml
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

## Event catalog

A readable event catalog is available at [`docs/ga_event_catalog.md`](docs/ga_event_catalog.md). It lists the collected earthquake events with magnitude, coordinates, depth, place, and candidate GNSS station counts within 200 km and 300 km for the current data-source adapter.

## Setup

Python package metadata is in `pyproject.toml`; the package requires Python 3.10 or newer.

With conda:

```bash
conda env create -f environment.yml
conda activate gnss-earthscope-pipeline
pip install -e .
```

External runtime tools are not vendored in this repository. Depending on the workflow, the local machine should provide tools such as `curl`, `jq`, `timeout`, `CRX2RNX`, and `pdp3`.

## Main workflow scripts

The current data-source adapter uses GA/Geoscience Australia high-rate GNSS access. These scripts can be treated as a reference adapter for adding other regional data sources.

Build or update the event/station database:

```bash
python scripts/build_ga_au_database.py --help
python scripts/update_ga_event_highrate_availability.py --help
```

Run event workflows:

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

## Tests

```bash
python -m unittest discover tests
```

---

# 中文说明

[English](#gnss-earthquake-pipeline) | 中文

本仓库是一个泛化的 GNSS 地震处理流程。流程围绕地震事件目录、高频 GNSS 台站可用性、事件窗口下载、PRIDE PPP-AR 处理、质量检查，以及标准化绘图/导出结果来组织。

这个流程不绑定某一个国家或台网。只要某个地区具备地震事件目录、台站元数据和高频 GNSS 数据接入，就可以接入并使用。当前代码中包含 GA/Geoscience Australia 适配器，它只是一个现有数据源实现；仓库整体按通用 pipeline 来呈现。

公开仓库只保留源码、工作流脚本、测试、可读事件摘要和 README 中展示用的少量图片。大型本地数据产品不会上传，包括下载的观测文件、SQLite 数据库、运行目录、标准化导出结果和批量生成图片。

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
gnss-earthquake-pipeline/
├── README.md
├── environment.yml
├── pyproject.toml
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

## 地震事件目录

可读的地震事件目录见 [`docs/ga_event_catalog.md`](docs/ga_event_catalog.md)。该文件列出了当前数据源适配器抓取到的地震事件，包括震级、经纬度、深度、地点，以及 200 km 和 300 km 范围内的候选 GNSS 台站数量。

## 环境安装

Python 包配置在 `pyproject.toml` 中，要求 Python 3.10 或更新版本。

使用 conda：

```bash
conda env create -f environment.yml
conda activate gnss-earthscope-pipeline
pip install -e .
```

外部运行依赖不会打包进本仓库。根据具体流程，本地机器需要安装 `curl`、`jq`、`timeout`、`CRX2RNX`、`pdp3` 等工具。

## 主要工作流脚本

当前数据源适配器使用 GA/Geoscience Australia 高频 GNSS 数据接入。这些脚本也可以作为接入其他区域数据源的参考实现。

构建或更新事件/台站数据库：

```bash
python scripts/build_ga_au_database.py --help
python scripts/update_ga_event_highrate_availability.py --help
```

运行事件工作流：

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

## 测试

```bash
python -m unittest discover tests
```
