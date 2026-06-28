# EarthScope MCP 使用手册

本项目提供一个本地 EarthScope MCP server，供 Claude Code 调用，用来查询地震事件覆盖状态、预览/导出 batch CSV，并运行当前 EarthScope/PRIDE workflow。

这个 MCP 是本地工具，不是远程 API 服务。用户需要把项目下载到自己的机器，配置本地 Python 环境、EarthScope CLI 登录状态和 PRIDE 运行依赖后使用。

## 1. 工具定位

当前 MCP server 只暴露三个核心工具：

```text
earthscope.overview
earthscope.batch
earthscope.run_batch
```

设计原则是少工具、统一入口：

- `overview`：只读查询入口，查看事件、覆盖状态、台站、batch summary 和环境检查。
- `batch`：batch CSV 准备入口，支持 preview 和 export。
- `run_batch`：真正执行 EarthScope/PRIDE workflow。

## 2. 代码和配置位置

MCP server 源码：

```text
src/gnss_eq/mcp_server.py
```

Python 命令行入口在 `pyproject.toml` 中定义：

```text
gnss-eq-mcp = gnss_eq.mcp_server:main
```

Claude Code MCP 配置文件：

```text
.mcp.json
```

当前 `.mcp.json` 使用仓库内相对包装脚本：

```json
{
  "mcpServers": {
    "earthscope": {
      "type": "stdio",
      "command": "./scripts/cli/gnss-eq-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

包装脚本位置：

```text
scripts/cli/gnss-eq-mcp
```

该脚本会先尝试调用当前环境里的 `gnss-eq-mcp`，如果找不到，则回退到：

```bash
python -m gnss_eq.mcp_server
```

因此用户需要先激活已安装本项目的 Python 环境，或者确保当前 `python` 可以 import `gnss_eq`。

## 3. 安装和本地环境

建议流程：

```bash
git clone <repo-url>
cd gnss-earthscope-pipeline
conda env create -f environment.yml
conda activate gnss-earthscope-pipeline
pip install -e .[mcp]
```

也可以使用已有 Python 环境，但需要保证：

```bash
python -c "import gnss_eq"
gnss-eq --help
gnss-eq-mcp
```

可正常运行。

运行 workflow 还需要外部程序在 `PATH` 中可用，或通过环境变量显式配置：

```text
es          EarthScope CLI
curl
jq
CRX2RNX
pdp3        PRIDE PPP-AR 程序
timeout
```

可选环境变量：

```text
EARTHSCOPE_ENV_BIN   EarthScope/Python 环境 bin 目录
PRIDE_BIN_DIR        pdp3 所在目录
LOCAL_BIN_DIR        其他本地工具目录
```

这些环境变量不应写成本机绝对默认值；如果用户机器上工具已经在 `PATH` 中，则不需要设置。

## 4. EarthScope 登录和环境检查

EarthScope/GAGE 数据访问需要本机 EarthScope CLI 登录：

```bash
es login
```

如果使用代理导致登录失败，可以临时绕过代理：

```bash
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
es login
```

登录后检查 token：

```bash
es user get-access-token
```

不要把 token 内容粘贴到聊天或文档里。

本项目的环境检查命令：

```bash
gnss-eq check-env
```

正常时会看到：

```text
OK	EarthScope auth	access token available
```

如果授权失败，会提示：

```text
FAIL	EarthScope auth	...; run: es login
```

在 MCP 中可以通过 `overview` 附带环境检查：

```text
earthscope.overview(view="coverage", source="earthscope", include_env=true)
```

注意：

- access token 通常是短期 token。
- CLI 会使用 refresh token 自动刷新。
- 如果 refresh token 失效或网络/代理阻断，需要重新 `es login`。

## 5. 数据源

`overview` 当前支持这些查询数据源：

```text
source="earthscope"
source="earthscope_nonconus"
source="geonet"
source="paper"
```

其中 `earthscope_nonconus` 是兼容别名。MCP 不暴露 CDDIS、GA/Geoscience Australia、RING/FReDNet、EPOS/GLASS 或 RENAG 的 batch/run 支持；这些代码即使保留在仓库中，也分别属于 research 或 parked exploratory 适配器。当前仓库级数据源优先级见 [`docs/data_sources.md`](data_sources.md)。

### 5.1 EarthScope / GAGE 数据源

默认数据源：

```text
source="earthscope"
```

`earthscope` 是统一的 EarthScope/GAGE 数据源，覆盖美国区域和可由 EarthScope/GAGE 台站处理的美国周边区域。用户通常不需要区分美国本土和 non-CONUS；MCP 会根据 `event_id` 自动选择底层数据库。

主要读取：

```text
data/earthscope_availability/earthscope_1hz.sqlite
data/earthscope_availability/earthscope_nonconus_1hz.sqlite
scripts/workflows/current_pipeline.sh list-events
runs/<event-id>/workflow-*
```

用于查看 EarthScope 候选事件、已有 workflow 输出和历史 normalized 标签。

兼容说明：`source="earthscope_nonconus"` 仍可用于旧调用，但它只是限制查询 non-CONUS 底层库的兼容别名；新调用推荐统一使用 `source="earthscope"`。

### 5.2 GeoNet / 新西兰数据源

```text
source="geonet"
```

主要读取：

```text
data/geonet_availability/geonet_1hz.sqlite
```

相关表：

```text
geonet_m6plus_events_nz
event_highrate_day_availability
event_geonet_station_candidates
```

GeoNet 数据源不使用 EarthScope `es login` token。

### 5.3 Paper / 全球论文历史数据源

```text
source="paper"
```

读取旧 collector 中的全球论文/历史 normalized 数据：

```text
../openclaw-gnss-collector-agent/data/gnss_data/normalized
```

这是只读数据源，用于检索已有论文收集数据。不支持 `stations` 视图，也不接入 `batch` / `run_batch`。

## 6. `earthscope.overview`

统一只读查询入口。

参数：

```text
view         coverage/events/summary/stations，默认 coverage
event_id     可选；stations 视图必填
limit        返回条数上限，默认 50
include_env  是否附带 gnss-eq check-env，默认 false
source       earthscope/geonet/paper，默认 earthscope；earthscope_nonconus 仅作为兼容别名
```

### 6.1 `view="coverage"`

列出候选事件，并计算覆盖状态。

示例：

```text
earthscope.overview(view="coverage", source="earthscope", limit=100)
earthscope.overview(view="coverage", source="geonet", limit=100)
earthscope.overview(view="coverage", source="paper", limit=100)
```

关键字段：

```text
event_id
magnitude
event_date
place
stations_200km
stations_300km
existing_data_status
existing_station_count
coverage_status
priority
```

`coverage_status`：

```text
WORKFLOW_DONE          当前 workflow 已经跑过
COLLECTED_NORMALIZED   已有历史 collected/normalized 数据
BOTH                   两边都有
MISSING                两边都没有
```

`priority`：

```text
HIGH     MISSING 且 200km 台站数 >= 20
MEDIUM   MISSING 且 200km 台站数 >= 5
LOW      MISSING 且 200km 台站数 < 5
SKIP     已有 workflow 或 collected 数据
```

### 6.2 `view="events"`

只列事件，不计算 workflow 覆盖状态。

示例：

```text
earthscope.overview(view="events", source="earthscope", limit=20)
earthscope.overview(view="events", source="geonet", limit=20)
earthscope.overview(view="events", source="paper", limit=20)
```

### 6.3 `view="stations"`

查询某个事件的候选台站。

EarthScope 示例：

```text
earthscope.overview(view="stations", source="earthscope", event_id="nc73666231", limit=100)
earthscope.overview(view="stations", source="earthscope", event_id="us7000irjd", limit=50)
```

GeoNet 示例：

```text
earthscope.overview(view="stations", source="geonet", event_id="2016p858000", limit=100)
```

Paper source 不支持 stations 视图。

### 6.4 `view="summary"`

读取 batch summary。

示例：

```text
earthscope.overview(view="summary")
earthscope.overview(view="summary", event_id="nc73666231")
```

## 7. `earthscope.batch`

batch CSV 准备入口。它不执行 PRIDE workflow，只负责 preview 或 export CSV。该工具面向当前 EarthScope pipeline；GeoNet、CDDIS 和 parked adapters 不通过这个 MCP 工具导出 batch。

参数：

```text
event_id          事件 ID
mode              preview 或 export，默认 preview
radius_km         200 或 300，默认 200
include_existing  是否允许已有 HAS_NORMALIZED 的事件导出，默认 false
source            earthscope，默认 earthscope；earthscope_nonconus 仅作为兼容别名
```

### 7.1 Preview

示例：

```text
earthscope.batch(event_id="nc73666231", mode="preview", radius_km=200)
earthscope.batch(event_id="us7000irjd", mode="preview", radius_km=300, source="earthscope")
```

返回内容包括：

```text
station_count
csv_path
has_existing_normalized
would_fail_without_include_existing
would_export
```

### 7.2 Export

示例：

```text
earthscope.batch(event_id="nc73666231", mode="export", radius_km=200)
earthscope.batch(event_id="us7000irjd", mode="export", radius_km=300, source="earthscope")
```

生成：

```text
data/batches/nc73666231-200km.csv
```

如果事件已有 normalized 数据，默认会拒绝导出，需要：

```text
earthscope.batch(event_id="ci38457511", mode="export", radius_km=200, include_existing=true)
```

## 8. `earthscope.run_batch`

真正运行 EarthScope/PRIDE workflow。该工具调用 `scripts/workflows/current_pipeline.sh`，不运行 GeoNet、CDDIS、GA、RING、EPOS 或 RENAG workflow。

参数：

```text
csv                    batch CSV 路径，必须在 data/batches/ 下
timeout                超时时间，默认 3600 秒
process_jobs           每个事件内并行运行的 station PRIDE jobs 数，默认 1；大事件建议从 5 开始
cleanup_pride_workdir  成功后清理 PRIDE 中间文件
cleanup_obs            成功后清理 canonical obs 文件
rerun_ok               是否重跑 batch 中已标记 OK 的行
source                 workflow 使用的数据源/坐标库，默认 earthscope；MCP 会按 batch 内 event_id 自动选择 EarthScope 底层 DB
use_verified_files     是否优先使用 verified first_obs_url 直接下载；默认 false，保持原 product API 路径
```

示例：

```text
earthscope.run_batch(csv="data/batches/nc73666231-200km.csv", timeout=3600)
```

大事件需要加快站点级 PRIDE 处理时，可以保持事件串行、只并行当前事件内的 station jobs：

```text
earthscope.run_batch(
    csv="data/batches/nonconus-priority8-300km.csv",
    timeout=10800,
    process_jobs=5,
    cleanup_pride_workdir=true,
    cleanup_obs=true,
    rerun_ok=true,
    source="earthscope",
    use_verified_files=true,
)
```

输出目录：

```text
runs/<event-id>/workflow-<timestamp>/
```

典型输出文件：

```text
reports/workflow-summary.md
reports/workflow-summary.json
reports/workflow-summary.tsv
reports/kin-quality.tsv
reports/kin-quality.json
manifests/obs-validation.tsv
manifests/kin-files.txt
```

当前 workflow 的成功标准以可用 `kin_*` 和质量结果为主。默认清理 obs 后，如果 `kin_*` 已生成且质量不是 `FAIL`，不应因为 canonical obs 文件被删除而判定 workflow 失败。

## 9. 典型使用流程

### 9.1 查看当前候选和覆盖状态

```text
earthscope.overview(view="coverage", source="earthscope", limit=100)
```

### 9.2 找一个值得继续跑的事件

优先选择：

```text
coverage_status = MISSING
priority = HIGH 或 MEDIUM
```

### 9.3 预览 batch

```text
earthscope.batch(event_id="EVENT_ID", mode="preview", radius_km=200)
```

### 9.4 导出 batch CSV

```text
earthscope.batch(event_id="EVENT_ID", mode="export", radius_km=200)
```

### 9.5 运行 workflow

```text
earthscope.run_batch(csv="data/batches/EVENT_ID-200km.csv", timeout=3600)
```

### 9.6 查看运行结果

```text
earthscope.overview(view="summary", event_id="EVENT_ID")
```

## 10. 自然语言示例

在 Claude Code 中可以直接说：

```text
检查一下 EarthScope workflow 环境和授权
看一下当前有哪些事件值得继续跑
预览 nc73666231 的 200 公里 batch
导出 nc73666231 的 200 公里 batch CSV
运行 data/batches/nc73666231-200km.csv 这个 batch，timeout 3600 秒
查看 nc73666231 的 batch summary
看一下 paper source 里收集了多少事件
看一下新西兰 GeoNet 已经跑了哪些事件
```

## 11. 常见问题

### 11.1 EarthScope auth 失败

现象：

```text
FAIL	EarthScope auth	...; run: es login
```

处理：

```bash
es login
```

如果代理导致登录失败，可以临时关闭代理：

```bash
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
es login
```

### 11.2 `pdp3` 找不到

检查：

```bash
which pdp3
```

如果不在 `PATH` 中，设置：

```bash
export PRIDE_BIN_DIR=/path/to/pride/bin
export PATH="$PRIDE_BIN_DIR:$PATH"
```

### 11.3 MCP 找不到 `gnss_eq`

说明当前 Claude Code 启动 MCP 时用的 Python 环境没有安装本项目。

处理：

```bash
pip install -e .[mcp]
python -c "import gnss_eq"
```

或把 `.mcp.json` 的 command 指向用户自己的环境包装脚本。

### 11.4 `run_batch` 下载失败但已有 `kin_*`

如果本地已有 PRIDE 输出或 `kin_*`，workflow 可能仍能完成质量检查。当前成功标准以可用 `kin_*` 和质量结果为主，不再把清理后的 obs 缺失作为硬失败。

### 11.5 Paper source 和 workflow 的关系

`source="paper"` 只用于查询历史论文/收集数据，不参与 EarthScope batch 导出和 workflow 运行。要运行 workflow，请使用 `source="earthscope"` 的事件和 `earthscope.batch` / `earthscope.run_batch`。
