# 公开 1 Hz GNSS 数据源调研记录

检查日期：2026-04-28；追加核实：2026-05-08

本文记录可用于扩展地震 GNSS 数据集的公开 1 Hz / high-rate GNSS 数据源。目标是补充当前美国事件样本之外的区域，减少与已有美国数据的重复。

## 当前仓库状态

本文是数据源调研和历史接入记录，不等同于当前研发优先级。当前仓库的主力 operational 数据源是 EarthScope/GAGE 和 GeoNet；CDDIS 保留为 research/experimental 数据源；GA/Geoscience Australia、RING/FReDNet、EPOS/GLASS、RENAG 以及其他区域源暂时属于 parked/exploratory，不是当前研究重点。当前优先级以 [`docs/data_sources.md`](data_sources.md) 为准。

## 总体结论

最值得优先接入的非美国数据源是：

1. GeoNet / PositioNZ，新西兰及 Kermadec 区域
2. Geoscience Australia / APREF，澳大利亚及亚太区域
3. CSN Chile，智利俯冲带，但需等待数据服务可访问后再实现
4. 日本 GSI GEONET，质量高但主要是事件级申请数据
5. EarthScope/GAGE，作为可复用补充源，但 1 Hz high-rate 主体仍是美国本土
6. CDDIS / IGS high-rate，全球稀疏兜底源
7. FReDNet / OGS Italy，意大利及亚得里亚区域补充源
8. EPOS GNSS Data Gateway / GLASS，欧洲联合入口，可用于发现 high-rate 文件，但需逐站确认覆盖
9. Rénag / Epos-France，法国及周边，公开 1 秒 RINEX，许可清楚
10. NSGI / Kadaster，荷兰及加勒比荷属站点，目录式 15 分钟 1 秒 RINEX，适合作为低地国家/加勒比补充
11. 台湾 GDMS / CWA / IES，需账号和 RINEX 采样率实测确认

EarthScope/GAGE 需要单独说明：它不是美国本土专用数据源，官网确认其 GNSS 归档包含全球分布的永久站，NOTA 也覆盖美洲 20 多个国家。但在线 1 Hz high-rate 单日目录快照显示，美国本土仍占绝大多数。因此它适合复用现有下载流程去挖 Mexico、Caribbean/Central America、Alaska/Aleutians、Antarctica 等非 CONUS 子集，但不能作为扩充非美国事件的主力来源。

上面的调研排序保留了当时对公开数据源潜力的判断；当前实现重点已经收敛到 EarthScope/GAGE 和 GeoNet，GA 等原型代码只作为保留适配器存在。

## 数据源评估

| 优先级 | 数据源 | 区域 | 1 Hz 证据 | 批量访问方式 | 当前判断 |
| --- | --- | --- | --- | --- | --- |
| 1 | GeoNet / PositioNZ | 新西兰、Kermadec、邻近西南太平洋 | GeoNet 文档说明有 1 秒 GNSS 数据和事件 high-rate 数据。实测 `gnss/rinex1Hz/...` 可按年/年积日枚举；公开 S3 中也可列出同一批 15 分钟、1 秒 RINEX 文件。 | 公开 HTTPS 目录、公开 S3 `ListBucket`、GeoNet network API。 | 最适合优先实现。开放、可枚举、地震相关性强。 |
| 1 | Geoscience Australia / APREF | 澳大利亚、太平洋岛屿、亚太参考框架站 | 官方文档列出 high-rate 观测文件为 15 分钟、1 秒采样 RINEX/Hatanaka 文件。实测 API 返回 `filePeriod=15M` 观测文件和签名 S3 下载链接。 | 公开 Web API、S3、SFTP、浏览器应用。API：`https://data.gnss.ga.gov.au/api/rinexFiles`。 | 工程接入条件很好。high-rate 只覆盖部分站点，需要做事件和台站筛选。 |
| 2 | CSN Chile | 智利俯冲带 | CSN 数据政策说明连续 GNSS 以 1 Hz Hatanaka RINEX 发布。 | 理论上为 `gps.csn.uchile.cl/data/` 目录式访问，但 2026-04-28 实测跳转到 `=503`。 | 科学价值和强震样本潜力都高，但要先重新确认服务可访问性。 |
| 2 | 日本 GSI GEONET / JSURVEY | 日本 | GSI 和 JSURVEY 页面列出 1 秒 RINEX/BINEX 事件数据；GSI 明确 1 秒值只在大地震等情况下保存，2015 年前为 G4 RINEX，2016 年后为 G5 BINEX。 | 不适合公开爬取。GSI 需提供申请；JSURVEY 为付费介质服务。 | 台站密度和事件质量很好，但不适合作为自动批量公开源。更适合按事件申请后手动导入。 |
| 2 | EarthScope/GAGE GNSS 归档 | 全球永久 GNSS 归档；NOTA 密集覆盖美洲，包含 Alaska、CONUS、Puerto Rico、Mexico/TLALOCNet、Caribbean/COCONet、Central America，以及少量其他全球站 | GAGE GPS/GNSS 页面说明数据中心管理 thousands of globally distributed permanent stations。文件服务器布局说明 `/archive/gnss/highrate[/N-Hz]` 和 high-rate RINEX/Hatanaka 观测文件。实测 `2026/117` 的 1 Hz high-rate 在线目录返回 966 个站目录。 | 需要 EarthScope 登录 token。目录支持 `?list`、`?list&dirs`、`?list&dirs&uris`；台站 metadata 可通过 `https://web-services.unavco.org/gps/metadata/sites/v1` 查询。 | 可复用价值高，但非美国增量有限。应作为全球源使用，同时过滤已有美国重复事件和台站。 |
| 3 | CDDIS / IGS high-rate | 全球 IGS 网络 | NASA Earthdata 文档说明 high-rate GNSS sub-hourly 产品来自全球永久 GNSS 接收机，一般为 1 秒 / 15 分钟文件。 | CDDIS 归档，需要 Earthdata 认证。 | 全球兜底源，但相对区域台网稀疏。 |
| 3 | EPOS GNSS Data Gateway / GLASS | 欧洲，含部分 EPN、Rénag、RING/FReDNet 等区域网络 | 官方说明 Data Gateway 可通过 Web、command line client 和 API 搜索下载欧洲 GNSS 数据；GLASS API 有 high-rate RINEX metadata/URL 端点。 | 公开 API，例如 `/files/highrate/station-marker/{station}/{format}`；也有 bbox station 查询。 | 适合做欧洲 high-rate 元数据发现层，但文件覆盖和许可来自各节点，实际下载器需要按 provider 分支处理。 |
| 3 | FReDNet / OGS | 意大利东北部、Friuli、Adria 微板块边界及邻区 | FReDNet 文档说明数据中心提供 hourly/daily RINEX，采样率 1 秒或 30 秒；站点页有 `RINEX files - 1s` 下载。 | 数据中心和请求模块；另有 OGS GLASS node `gnssdata-epos.ogs.it`。 | 可作为意大利/亚得里亚区域补充源。许可 CC BY 4.0，工程上需要继续抓取真实下载 URL 形态。 |
| 3 | Rénag / Epos-France | 法国科学 GNSS 网络，含 Alps/Pyrenees 等构造区 | 官方说明 Rénag 数据 public/free，1s/1h high-frequency RINEX；`https://renag.resif.fr/pub/rinex3_1s/` 公开列出 2019-2026 年目录。 | 公开 HTTPS/FTP，目录结构 `YEAR/DOY/rinex`。 | 接入条件好，许可 CC-BY 4.0；优先级高于只走 EPOS 元数据层。 |
| 3 | NSGI / Kadaster | 荷兰，另见 Aruba 等荷属加勒比站 | 官方说明 highrate RINEX 按 product/year/day-of-year 通过 HTTPS 提供；实测 `data/highrate/2026/128/` 列出 `*_15M_01S_MO.crx.gz`。 | 公开 HTTPS 目录：`https://gnss-data.kadaster.nl/data/highrate/<year>/<doy>/`。 | 机器可枚举、无需登录，适合作为欧洲西部/加勒比小区域补充；但许可证页面不如 Rénag/FReDNet 明确，接入前需补确认引用/许可。 |
| 4 | 台湾 GDMS / CWA / IES / TGM | 台湾 | GDMS GNSS 下载页存在，TGM 说明 IES 数据下载门户可批量下载 RINEX；但 GDMS 页面要求登录，TGM 明确只提供 IES 维护站超过 6 个月的数据。 | GDMS 需登录，GNSS 全测站一次选择时间不超过 7 天，外单位 GNSS_IES/GNSS_ETEC 只提供 30 日前数据；TGM 需门户下载。 | 区域很有价值，但自动化前必须确认账号、下载流程、许可和真实 RINEX header `INTERVAL`。 |

## EarthScope/GAGE 重点修正

EarthScope/GAGE 确实包含世界各地的 GNSS 台站，但用于 1 Hz high-rate 数据扩展时，要区分“归档覆盖全球”和“1 Hz high-rate 可用站点分布”。

官网和在线接口检查结果：

- EarthScope NOTA 页面说明：NOTA 覆盖 20 多个国家，包含 1200 多个连续运行仪器，范围从 Aleutian Islands 到 Caribbean。
- NOTA 集成了 PBO、TLALOCNet 和 COCONet：
  - PBO：Alaska、continental US、Puerto Rico
  - TLALOCNet：Mexico 40 站
  - COCONet：Caribbean 85 站
- GAGE GPS/GNSS 页面说明：数据中心管理来自 thousands of globally distributed permanent stations 的数据。
- 官方 metadata API 全世界 bbox 查询返回 4546 个 GNSS site metadata records。
- 使用 EarthScope token 实测 high-rate 目录：
  `https://gage-data.earthscope.org/archive/gnss/highrate/1-Hz/rinex/2026/117/?list&dirs&uris`
- 该 UTC 日期 2026-04-27 的在线目录返回 966 个 1 Hz high-rate 站目录。

这 966 个站按官网 metadata 粗分：

| 区域 | 站数 | 占比 |
| --- | ---: | ---: |
| CONUS，美国本土 | 825 | 85.4% |
| Alaska/Aleutians | 70 | 7.2% |
| Caribbean/Central America | 42 | 4.3% |
| Mexico | 11 | 1.1% |
| Antarctica | 5 | 0.5% |
| Other | 13 | 1.3% |

因此，EarthScope/GAGE 的正确使用策略是：

- 不能把 EarthScope 当成美国本土专用源；它有全球和泛美洲覆盖。
- 也不能把 EarthScope 当成扩非美国事件的主力；1 Hz high-rate 单日可用站点高度集中在美国本土。
- 后续应从在线 metadata API 和 high-rate 目录实时生成候选站，而不是依赖本地不完整站表。
- 筛选时优先排除已有美国重复事件和站点。
- 非美国方向优先挖 Mexico/TLALOCNet、Caribbean/COCONet、Central America、Antarctica、少量 other global stations。

## 接入备注

### 管线隔离原则

后续接入 GeoNet、GA、CSN 等非 EarthScope 数据源时，应保持“采集层独立、后处理层可复用”的边界，避免把 EarthScope 的登录、目录结构、站名格式和 availability 数据库假设扩散到其他数据源。

建议边界如下：

- 每个数据源单独建立采集器目录，例如 `tools/geonet_downloader/`、`tools/ga_downloader/`。GeoNet 不调用 `tools/earthscope_downloader/` 下的脚本。
- 每个数据源单独保存原始 inventory、availability、下载 manifest 和中间文件，例如 `data/geonet_*`、`runs/<event>/download/raw-geonet-1hz/`。不要写入 `data/earthscope_metadata/` 或 `data/earthscope_availability/`。
- 每个数据源有自己的事件候选 CSV 或 manifest，字段可以对齐最终工作流需要的通用字段，但不要复用带有 EarthScope 语义的文件名或状态列含义。
- 可以复用真正与数据源无关的模块：
  - `tools/pride_processor/process_event_window.sh`：只依赖本地 RINEX obs 文件和事件时间，适合作为后处理入口。
  - `tools/pride_processor/plot_enu_svg.py`：只处理 PRIDE 输出结果，适合复用。
  - `scripts/quality/compute_kin_quality.py`：如果输入仍是同一类 PRIDE kin 输出，可复用。
- 不建议直接复用的模块：
  - `tools/earthscope_downloader/*`：包含 EarthScope/GAGE URL、token、目录、RINEX 命名和产品查询假设。
  - `scripts/availability/update_earthscope_availability.py`：绑定 EarthScope high-rate 目录和 SQLite schema。
  - `scripts/workflows/run_event_1hz_pride_workflow.sh`、`scripts/workflows/run_event_batch_workflow.sh`：当前把下载、验证、PRIDE、绘图串成 EarthScope 事件工作流；GeoNet 可以借鉴输出约定，但应新建自己的入口，避免隐藏依赖。

推荐 GeoNet 的最小独立实现形态：

- `tools/geonet_downloader/list_geonet_1hz.py`：枚举 `rinex1Hz/<year>/<doy>/` 的文件，生成当天站点 availability。
- `tools/geonet_downloader/fetch_geonet_1hz.py`：按事件时间窗口和站点列表下载 15 分钟 RINEX 文件。
- `tools/geonet_downloader/geonet_station_inventory.py`：调用 GeoNet `network/station?sensorType=8` 和 `network/sensors`，输出本源自己的站点 inventory。
- `scripts/workflows/run_geonet_event_1hz_pride_workflow.sh`：GeoNet 专用事件入口。它负责 GeoNet 下载和验证，下载完成后再调用通用 PRIDE 后处理。
- `scripts/workflows/run_geonet_batch_workflow.sh`：GeoNet 专用批处理入口。它可以保持与现有 CSV 类似的事件字段，但不复用 EarthScope batch 脚本。

当前已实现的 GeoNet 独立管线：

- `tools/geonet_downloader/geonet_common.py`：GeoNet 专用公共函数，只在 GeoNet 下载器内部复用。
- `tools/geonet_downloader/geonet_station_inventory.py`：生成 GeoNet GNSS/GPS active 站表。
- `tools/geonet_downloader/list_geonet_1hz.py`：解析 GeoNet 1 Hz 日目录，输出文件级 availability。
- `tools/geonet_downloader/select_geonet_stations.py`：按事件半径选站，可叠加当天 1 Hz availability 过滤。
- `tools/geonet_downloader/fetch_geonet_1hz.py`：下载事件窗口覆盖的 15 分钟 RINEX，并按站合并为一个本地 obs 文件。默认 `--merge-method auto`，本机有 `gfzrnx` 时使用 `gfzrnx -finp ... -fout ... -kv -try_append 900` 进行 splice；没有 `gfzrnx` 时回退到 Python 文本级合并。可用 `--merge-method gfzrnx` 强制要求 `gfzrnx`，或用 `--merge-method python` 强制回退实现。
- `tools/geonet_downloader/fetch_geonet_event_highrate.py`：下载 GeoNet `event.highrate/1hz/rinex` 历史事件文件，支持 `*.d.Z`、`*.o.gz`、`*.rnx.gz`，并转换/解压到 `data/obs/<event_id>/`。
- `tools/pride_processor/estimate_obs_event_window.py`：从 RINEX epoch 覆盖估计事件两侧可用的对称处理窗口。该工具不绑定 GeoNet，可用于任何已落盘 obs 文件。
- `scripts/workflows/run_geonet_event_1hz_pride_workflow.sh`：GeoNet 单事件 workflow，输出目录结构与既有 workflow 对齐，但下载阶段完全独立。`--download-source rolling` 用滚动 15 分钟源；`--download-source event-highrate` 用历史事件归档。对 `event-highrate`，如果用户没有显式传 `--hours`，workflow 会按已下载 obs 的共同覆盖自动收缩 PRIDE 和质量评估窗口。
- `scripts/workflows/run_geonet_batch_workflow.sh`：GeoNet 批处理 workflow，支持 CSV resume、自动选站、`--download-source event-highrate` 和 `--process-jobs` 并行透传。
- `scripts/database/build_geonet_nz_database.py`：创建 GeoNet 新西兰/Kermadec M6+ 地震-台站 SQLite 数据库。

当前 GeoNet 新西兰数据库：

- SQLite：`data/geonet_availability/geonet_1hz.sqlite`
- 事件表：`geonet_m6plus_events_nz`
- 台站表：`geonet_gnss_stations`
- 事件-台站候选表：`event_geonet_station_candidates`
- 台站日 1 Hz availability 表：`station_day_availability`
- 批处理 CSV：`data/geonet_batches/geonet_m6plus_nz_candidates_300km.csv`
- 构建参数：GeoNet FDSN event，`2010-01-01T00:00:00` 到 `2026-04-29T00:00:00`，`minmagnitude=6`，区域为新西兰/Kermadec 跨日期线 bbox：`lat -55..-25, lon 160..180` 和 `lat -55..-25, lon -180..-170`。
- 当前构建结果：44 个 M6+ 事件、258 个唯一 GNSS 台站、200 km 候选 617 行、300 km 候选 1250 行；300 km 批处理 CSV 中 28 个事件有候选站，16 个远海事件暂无 300 km 内候选站。

历史事件入库验证，2026-04-29：

- 使用 GeoNet 官网 FDSN event API 和官网 GNSS station metadata API 重新在线查询 `2010-01-01T00:00:00` 到 `2026-04-29T00:00:00` 的新西兰/Kermadec M6+ 地震，临时写入 `/tmp/geonet_history_check.sqlite` 成功。
- 临时库 `PRAGMA integrity_check` 返回 `ok`。
- 事件表写入 44 个唯一事件，时间范围为 `2010-08-01` 到 `2025-07-07`；事件必填字段 `event_id`、`time_utc`、`magnitude`、`latitude`、`longitude` 无空值。
- 台站表写入 258 个唯一 GNSS 台站；官网 metadata 原始 features 为 259 个，入库后按 4 字符 station code 去重。
- 候选表外键检查无孤立记录；200 km 候选 617 行、覆盖 26 个事件和 178 个站，300 km 候选 1250 行、覆盖 28 个事件和 200 个站。
- 结论：GeoNet 历史地震事件和事件-台站候选关系可以直接录入数据库。需要注意的是，普通 `rinex1Hz` 目录只滚动保留近两个月左右数据；因此历史事件“可入库”不等于历史 1 Hz RINEX 已确认可下载。历史下载还需要继续验证 `gnss/event.highrate/` 或其他归档路径。

历史 1 Hz RINEX 下载验证，2026-04-29：

- 普通连续 1 Hz 目录 `gnss/rinex1Hz/<year>/<doy>/` 不保留长期历史。实测 `https://data.geonet.org.nz/v1/data/gnss/rinex1Hz/2013/202/` 返回 404；S3 前缀 `gnss/rinex1Hz/2013/202/` 返回 `KeyCount=0`。
- 历史事件数据在 GeoNet AWS Open Data 的 `gnss/event.highrate/` 下。顶层包含 `1hz/raw/`、`1hz/rinex/`、`10hz/raw/`、`10hz/rinex/`。
- 官方 `README.gnsshighrate` 说明 `raw` 目录是接收机原始 hourly 文件，`rinex` 目录是由相同 raw 文件拼接生成的 1 Hz 或 10 Hz daily RINEX；README 明确列出 2013 Cook Strait/Lake Grassmere、2014 Eketahuna、2014 Te Araroa、2016 East Cape、2016 Kaikoura、2019 Whakaari 等历史事件或专题高频数据。
- 在线枚举 `gnss/event.highrate/1hz/rinex/` 可见年份：2013、2014、2015、2016、2019、2020、2021、2022、2023、2025、2026。对应 1 Hz RINEX 日期前缀数量分别约为 134、193、7、62、41、2、8、1、1、9、7。
- 典型历史事件日可列出大量文件：
  - `2013/202`，Cook Strait M6.5，1 Hz RINEX/Hatanaka 文件约 160 个站。
  - `2013/228`，Lake Grassmere M6.5，约 171 个站。
  - `2016/318`，Kaikoura M7.8 及同日 M6+ 事件，约 73 个站。
  - `2021/063`，Te Araroa offshore M7.2，约 182 个站。
- 实际下载样例成功：`https://geonet-open-data.s3.amazonaws.com/gnss/event.highrate/1hz/rinex/2013/202/auck2020.13d.Z`，HEAD 返回 200，`Content-Length=15668169`。本地下载后文件约 15 MB，格式为 Unix compress 包裹的 Hatanaka compact RINEX `*.d.Z`。
- 本机可用 `/usr/bin/uncompress` 解压为 `*.d`，并可用 `/home/lihe/.local/bin/crx2rnx` 转为普通 RINEX `*.o`。样例 `auck2020.13d.Z` 转换后生成 `geonet_auck2020.13o`，RINEX header 为 2.11，前几个 epoch 为 `00:00:00`、`00:00:01`、`00:00:02`、`00:00:03`、`00:00:04`，确认是 1 秒采样。
- 将当前 `geonet_m6plus_events_nz` 的 44 个 M6+ 历史事件与 `event.highrate/1hz/rinex/<year>/<doy>/` 精确日期交叉匹配，19 个事件日有 1 Hz RINEX 可下载。2026-04-29 已用脚本 `scripts/availability/update_geonet_event_highrate_availability.py` 逐事件日重新枚举 S3，并写入本地数据集：
  - SQLite 汇总表：`event_highrate_day_availability`
  - SQLite 文件表：`event_highrate_station_files`
  - 事件汇总 CSV：`data/geonet_availability/geonet_event_highrate_m6plus_availability.csv`
  - 文件明细 TSV：`data/geonet_availability/geonet_event_highrate_m6plus_files.tsv`
  - 可直接批处理的 300 km 候选 CSV：`data/geonet_batches/geonet_m6plus_nz_event_highrate_candidates_300km.csv`
- 本次写入结果：44 个 M6+ 事件已检查，19 个事件有 high-rate 1 Hz RINEX，文件明细 1036 行，去重台站 206 个；这 19 个事件均至少有 1 个 300 km 内候选台站与实际文件匹配。
  - 2013：`2013p543824`、`2013p613797`、`2013p944608`
  - 2014：`2014p051675`、`2014p770859`、`2014p864702`
  - 2015：`2015p305812`
  - 2016：`2016p661332`、`2016p661400`、`2016p661723`、`2016p858000`、`2016p858007`、`2016p858021`、`2016p858055`、`2016p858094`、`2016p859524`
  - 2021：`2021p169083`
  - 2025：`2025p224518`、`2025p506857`
- 19 个事件的日目录文件数、去重台站数、以及与 300 km 候选台站的交集如下：

| 事件 ID | 日期 | 文件数 | 去重台站数 | 300 km 内有文件台站数 |
| --- | --- | ---: | ---: | ---: |
| `2013p543824` | 2013-07-21 | 160 | 160 | 84 |
| `2013p613797` | 2013-08-16 | 171 | 171 | 81 |
| `2013p944608` | 2013-12-16 | 11 | 11 | 4 |
| `2014p051675` | 2014-01-20 | 26 | 26 | 25 |
| `2014p770859` | 2014-10-13 | 13 | 13 | 1 |
| `2014p864702` | 2014-11-16 | 8 | 8 | 7 |
| `2015p305812` | 2015-04-24 | 5 | 5 | 3 |
| `2016p661332` | 2016-09-01 | 16 | 16 | 8 |
| `2016p661400` | 2016-09-01 | 16 | 16 | 8 |
| `2016p661723` | 2016-09-01 | 16 | 16 | 8 |
| `2016p858000` | 2016-11-13 | 73 | 73 | 49 |
| `2016p858007` | 2016-11-13 | 73 | 73 | 46 |
| `2016p858021` | 2016-11-13 | 73 | 73 | 48 |
| `2016p858055` | 2016-11-13 | 73 | 73 | 48 |
| `2016p858094` | 2016-11-13 | 73 | 73 | 48 |
| `2016p859524` | 2016-11-14 | 35 | 35 | 34 |
| `2021p169083` | 2021-03-04 | 182 | 182 | 22 |
| `2025p224518` | 2025-03-25 | 6 | 6 | 3 |
| `2025p506857` | 2025-07-07 | 6 | 6 | 5 |

- 旧 normalized 数据集重复标记，2026-04-29：参考美国事件库的 `existing_data_status` 方式，脚本 `scripts/normalize/sync_geonet_normalized_existing_labels.py` 已给 `geonet_m6plus_events_nz` 增加并写入 `existing_data_status`、`existing_data_source`、`existing_dataset_dir`、`existing_station_count`、`existing_waveform_file`、`existing_event_file`、`existing_updated_at` 字段。按 600 秒时间窗、50 km 空间窗与 `/home/lihe/study/eq_collect/openclaw-gnss-collector-agent/data/gnss_data/normalized` 匹配，当前只有 `2016p858000` 被标为 `HAS_NORMALIZED`，对应旧数据集 `kaikoura-2016-new-zealand`，旧数据集台站数 36。其余 18 个 GeoNet high-rate 事件未作为独立事件收集；其中 `2016p858007` 和 `2016p858021` 发生在旧 Kaikoura 主震短窗口内，但不标记为 `HAS_NORMALIZED`，避免后续批处理误判为独立事件已收集。
- 结论：GeoNet 历史 1 Hz RINEX 可以下载，但覆盖是事件归档式的，不是所有历史 M6+ 每日连续覆盖。下载器需要新增 `event.highrate` 分支，支持列 `1hz/rinex/<year>/<doy>/`，并兼容三类文件形态：早期 RINEX 2 Hatanaka `*.d.Z`、2021 年样式的 RINEX 2 观测文件 `*.o.gz`、2025 年样式的 RINEX 3 `*_01S_MO.rnx.gz`。其中 `*.d.Z` 需要 `uncompress` 加 `crx2rnx`，`*.o.gz` 和 `*.rnx.gz` 主要是 gzip 解压后进入现有 PRIDE 后处理。
- 处理窗口策略，2026-04-29：GeoNet historical `event.highrate` 不能默认套用美国事件的 `±3h`。实测 `2015p305812` 的 `KAIK/HANM/MTJO` 文件只有 `03:00:00Z` 到 `03:59:59Z` 的 1 小时覆盖；现在 workflow 在 `--download-source event-highrate` 且未显式传 `--hours` 时，会从 RINEX epoch 自动估计共同覆盖，并把该事件收缩为 `±0.387778h`，PRIDE、绘图和质量统计均为 `OK`。若用户显式传 `--hours`，则尊重用户设置；可用 `--no-auto-hours` 关闭自动收缩。
- 端到端测试，2026-04-29：
  - `2015p305812`，台站 `KAIK HANM MTJO`，`--download-source event-highrate --process-jobs 2 --skip-download`，自动窗口 `0.387778h`，生成 3 个 kin、6 张 ENU 图，`download_status=REUSED`、`process_status=OK`、`plot_status=OK`、`quality_status=OK`。
  - `2025p224518`，台站 `PYGR BLUF MAVL`，`--download-source event-highrate --process-jobs 2 --hours 1`，生成 3 个 obs、3 个 kin、6 张 ENU 图，下载、PRIDE、绘图、质量统计全 `OK`。

GeoNet 单事件示例：

```bash
scripts/workflows/run_geonet_event_1hz_pride_workflow.sh \
  --event-id nz_demo \
  --event-time 2026-04-29T00:30:00Z \
  --stations "WGTN KAIK" \
  --hours 0.25 \
  --merge-method auto \
  --allow-partial
```

GeoNet 历史 `event.highrate` 示例，默认按 obs 覆盖自动选择处理窗口：

```bash
scripts/workflows/run_geonet_event_1hz_pride_workflow.sh \
  --event-id 2015p305812 \
  --event-time 2015-04-24T03:36:42Z \
  --download-source event-highrate \
  --stations "KAIK HANM MTJO" \
  --process-jobs 2 \
  --allow-partial
```

GeoNet 批处理 CSV 字段建议：

```csv
event_id,event_time,latitude,longitude,magnitude,radius_km,stations,status
nz_demo,2026-04-29T00:30:00Z,-41.5,174.0,6.5,,WGTN KAIK,
```

如果 `stations` 为空，批处理脚本可用 GeoNet inventory 自动选站：

```bash
tools/geonet_downloader/geonet_station_inventory.py \
  --out-csv data/geonet_inventory/geonet_gnss_stations.csv \
  --out-json data/geonet_inventory/geonet_gnss_stations.json

scripts/workflows/run_geonet_batch_workflow.sh \
  --csv data/geonet_batches/geonet_m6plus_nz_event_highrate_candidates_300km.csv \
  --download-source event-highrate \
  --process-jobs 2
```

### GeoNet

- 公开 1 Hz RINEX 目录：
  `https://data.geonet.org.nz/v1/data/gnss/rinex1Hz/<year>/<doy>/`
- 公开 S3 bucket：
  `https://geonet-open-data.s3.amazonaws.com/?list-type=2&prefix=gnss/rinex1Hz/`
- GNSS/GPS 站点 metadata API：
  `https://api.geonet.org.nz/network/station?sensorType=8&endDate=9999-01-01`
- 单站详细元数据 API 示例：
  `https://api.geonet.org.nz/network/sensors?sensorType=8&station=AUCK`
- 事件 high-rate 对象示例：
  `gnss/event.highrate/10hz/raw/<year>/<doy>/...`
- 2026-04-29 在线实测：
  - `https://data.geonet.org.nz/gnss/rinex1Hz/` 返回 301，并跳转到 `/v1/data/gnss/rinex1Hz/`。
  - `https://data.geonet.org.nz/v1/data/gnss/rinex1Hz/2026/` 可列目录，当前显示 2026 年第 057 到 119 天，符合官网“两个月滚动保留 1 秒数据”的说明。
  - 近三天 `2026/117`、`2026/118`、`2026/119` 的目录中，按 RINEX 文件名去重后每天都是 62 个实际有 1 Hz 文件的站点。
  - 当天 `2026/119` 目录中绝大多数为 `*00NZL` 站，另有 `SCTB00ATA`；样例站包括 `AUCK00NZL`、`WGTN00NZL`、`KAIK00NZL`、`GISB00NZL`、`TAUP00NZL`、`BLUF00NZL`、`CHTI00NZL`。
  - `https://api.geonet.org.nz/network/station?sensorType=8&endDate=9999-01-01` 返回 259 个 GNSS/GPS metadata features，其中 active 站点 216 个；active 网络粗分为 `CG` 152、`LI` 37、`GT` 9、`SA` 8、`XX` 6、`GN` 4。
  - 样例文件 `AUCK00NZL_S_20261190000_15M_01S_MO.rnx` 无需登录即可下载；HEAD 返回 200，文件大小约 6.24 MB。实测完整下载耗时约 3.3 秒。RINEX header 为 3.04，文件名和 header 均显示 15 分钟文件、1 秒观测、多星座观测。
  - RINEX header 注明数据按 Creative Commons Attribution 4.0 International licence 复用。
- 建议实现：
  先枚举新西兰/Kermadec 地震事件，按半径选站，再拉取事件窗口内 high-rate 或 1 秒 RINEX。

### Geoscience Australia / APREF

- 查询 API：
  `https://data.gnss.ga.gov.au/api/rinexFiles`
- 关键参数：
  `stationId`, `startDate`, `endDate`, `filePeriod=15M`, `fileType=obs`,
  `rinexVersion=2,3,4`, `metadataStatus=all`.
- 实测确认：
  `filePeriod=15M` 返回 15 分钟 high-rate 观测文件，并提供签名 S3 `fileLocation`。
- 建议实现：
  先建立 GA 台站 inventory，按事件半径选站，再查询事件窗口内 `15M` 观测文件。

### EarthScope/GAGE

- high-rate 1 Hz 根目录：
  `https://gage-data.earthscope.org/archive/gnss/highrate/1-Hz/rinex`
- 官方 station metadata API：
  `https://web-services.unavco.org/gps/metadata/sites/v1`
- 文件服务器访问方式：
  使用 EarthScope CLI 获取 token，并在请求中加入：
  `Authorization: Bearer $(es user get-access-token)`
- 目录枚举参数：
  `?list`, `?list&dirs`, `?list&dirs&uris`
- 建议实现：
  用线上 metadata API 和 high-rate 目录作为源数据，生成每日 station availability，再和事件目录做半径匹配；默认排除 CONUS，按需要决定是否保留 Alaska/Aleutians。

### CSN Chile

- 官方政策页说明连续 GNSS 为 1 Hz Hatanaka RINEX。
- 2026-04-28 实测：
  - `https://gps.csn.uchile.cl/data/` 跳转到 `=503`
  - HTTP 会重定向回 HTTPS
- 建议实现：
  周期性重试服务可用性；恢复后先验证已知站点/日期路径和 RINEX header，再写完整下载器。

### CDDIS / IGS

- 适合作为区域台网覆盖不足时的全球兜底源。
- 需要 Earthdata 登录/cookie/token 处理。
- 建议在 GeoNet、GA、EarthScope 非 CONUS 子集、CSN 等更高收益源之后实现。

### Japan GSI GEONET

- 存在 1 秒 RINEX/BINEX 事件数据，覆盖日本主要地震。
- 不适合公开目录批量爬取。
- 2026-05-08 重新核实：
  - GSI 说明“以 30 秒值为基本数据，但在大规模地震等时候保存 1 秒值”。
  - 2015 年以前 1 秒值保存为 G4 格式的 RINEX，2016 年以后保存为 G5 格式的 BINEX。
  - GSI“今後に向けたデータセット”页面公开了若干 M7+ 近海地震的历史 1 秒观测集，但页面强调用于以 download form 申请，且 1 秒数据“仅在必要范围内提供”。
  - JSURVEY 1-second RINEX/BINEX 页面说明 1 秒 RINEX 以 1 小时为单位，BINEX 以 1 日为单位，但服务是付费介质交付。
- 当前判断：
  - 不作为“公开批量下载源”实现下载器。
  - 可做事件清单和手动导入路径：先按日本 M7+ 事件整理 GSI 可申请数据集，申请后转换为本管线 obs cache。
  - 许可证/引用需要在每次申请返回的数据说明中确认，不能按开放目录默认处理。

### FReDNet / OGS

- 可能用于意大利及周边区域事件。
- 官方说明：
  - FReDNet 是 OGS 运行的连续 GPS/GNSS 网络，覆盖 Friuli Venezia Giulia、Veneto 和邻区，面向 Adria 微板块东北边界监测。
  - RINEX 数据按 hourly/daily 提供，采样率有 1 秒或 30 秒。
  - 数据使用 Creative Commons Attribution 4.0 International License，并要求引用 OGS 和 FReDNet。
- 2026-05-08 判断：
  - 科学区域有价值，尤其是意大利东北部、Alps/Adria 相关事件。
  - 自动化前还要继续确认稳定批量端点。优先尝试站点页面的 `RINEX files - 1s` 链接和 OGS GLASS node，而不是只解析交互页面。
  - 如果走 GLASS/EPOS，需要在 manifest 中保留原始 provider、license/citation 和 station marker。

### EPOS GNSS Data Gateway / GLASS

- 作用：
  - 欧洲 high-rate 数据发现层，而不是单一归档源。
  - 可通过 EPOS Web 门户、command line client 和 API 查找 GNSS 文件 metadata 和下载 URL。
- API 线索：
  - high-rate station 文件 API 形态：
    `https://gnssdata-epos.oca.eu/GlassFramework/webresources/files/highrate/station-marker/<STATION>/json?...`
  - station bbox API 形态：
    `https://gnssdata-epos.oca.eu/GlassFramework/webresources/stations/v2/highrate/bbox/<minlon>/<minlat>/<maxlon>/<maxlat>`
  - 2026-05-08 实测 `CASC00PRT` high-rate files API 返回空数组，说明需要先从门户/API 查 station/时间/provider 的正确组合，不能盲猜站名。
- 许可：
  - EPOS 层常见为 metadata/服务聚合，实际数据许可和引用通常归各 contributing data centre。
  - 下载 manifest 必须保存 `dataCenter/provider/license/citation` 字段，不能把 EPOS 统一入口等同为统一许可证。
- 当前判断：
  - 适合做欧洲候选台站和文件发现服务。
  - 真正稳定的下载实现应优先选择已验证的节点目录，例如 Rénag、NSGI、FReDNet/OGS，再用 EPOS 补充 metadata。

### Rénag / Epos-France

- 区域：
  法国科学 GNSS 网络，适合 Alps、Pyrenees、法国本土及近邻事件补充。
- 公开入口：
  - 数据服务说明页：`https://renag.resif.fr/english-technical-center/data-access/`
  - 1 秒 RINEX3 目录：`https://renag.resif.fr/pub/rinex3_1s/`
- 2026-05-08 实测：
  - `https://renag.resif.fr/pub/rinex3_1s/` 可匿名列目录，年份为 2019 到 2026。
  - `https://renag.resif.fr/pub/rinex3_1s/2026/` 可按年积日列目录。
  - 页面说明 Rénag GNSS 数据通过 public/free FTP server 或 HTTPS 提供；站点数据分为 1h/1s high frequency RINEX、daily RINEX、raw daily data、metadata。
- 许可：
  - 官方说明数据依据 Creative Commons Attribution 4.0 International License 分发。
- 建议实现：
  - 新建 `tools/renag_downloader/`，解析 `rinex3_1s/<year>/<doy>/`。
  - 文件名应按 RINEX3 long filename 解析，处理 `*.crx.gz` 或同类 Hatanaka/gzip 文件。
  - 先建立 station inventory，再按欧洲事件半径筛选。
- 试接入结果，2026-05-08：
  - 已新增最小工具：
    `tools/renag_downloader/list_renag_1hz.py`、`tools/renag_downloader/renag_station_inventory_from_day.py`、`scripts/database/build_renag_usgs_database.py`。
  - 事件目录先使用 USGS ComCat。原因是它与现有美国/GeoNet 入库字段容易对齐，跨国 bbox 查询也方便；法国/阿尔卑斯正式小震目录如需完整性，可再补 BCSF/RENASS 或 EMSC 目录。
  - 使用 USGS bbox `lat 41..52, lon -6..10`、`2019-01-01` 到 `2026-05-08`，`M5.5+` 没有事件；试接入降到 `M4.5+` 后得到 10 个候选事件。
  - 实测 `https://renag.resif.fr/pub/rinex3_1s/2026/128/`，解析到 120 个 1 小时、1 秒 `*.crx.gz` 文件，69 个唯一站。
  - 从 2026/128 RINEX header 抽取了 20 站样本 inventory，字段包括 station、经纬度、高程和源文件 URL。
  - 用 20 站样本 inventory、300 km 半径、事件日 availability 交叉后，10 个 USGS M4.5+ 候选中有 5 个事件匹配到 300 km 内当天 Rénag 1 Hz 台站，共 30 条事件-台站候选。
  - 输出：
    - `data/renag_availability/renag_1hz.sqlite`
    - `data/renag_availability/renag_1hz_2026_128.tsv`
    - `data/renag_inventory/renag_gnss_stations_sample20.csv`
    - `data/renag_batches/renag_usgs_m45_france_alps_sample20_candidates_300km.csv`
- 当前限制：
  - 站点 inventory 仍是样本，不是完整 Rénag 站表。
  - inventory 目前从 RINEX header 抽取坐标，工程可行但较慢；正式实现应优先找 Rénag/EPOS station metadata API 或缓存增量更新。
  - 当前 batch CSV 已可说明“事件日有 1 Hz 文件并按样本站坐标选站”，但还不是完整端到端 PRIDE workflow。

### NSGI / Kadaster

- 区域：
  荷兰 GNSS 数据中心，也包含 Aruba 等荷属加勒比站点；可补欧洲西部和加勒比小区域。
- 公开入口：
  - 数据说明：`https://www.nsgi.nl/referentiepunten-en-gnss-data/gnss-data/rinex-data`
  - highrate 目录：`https://gnss-data.kadaster.nl/data/highrate/`
- 2026-05-08 实测：
  - `https://gnss-data.kadaster.nl/data/highrate/` 可匿名列出 2019 到 2026 年目录。
  - `https://gnss-data.kadaster.nl/data/highrate/2026/` 可列出年积日目录。
  - `https://gnss-data.kadaster.nl/data/highrate/2026/128/` 可列出大量 15 分钟、1 秒、RINEX3/Hatanaka/gzip 文件，例如 `AMST00NLD_R_20261280000_15M_01S_MO.crx.gz`。
  - 官方说明文件结构为 `product/YYYY/DOY/`，product 包含 `hourly`、`daily`、`highrate`。
- 许可：
  - 当前页面确认 public HTTPS 数据目录和数据中心说明，但未在已查页面中明确看到 CC 许可证条款。
  - 接入前需要再确认 NSGI/Kadaster 的使用条款、引用要求和二次发布许可。
- 建议实现：
  - 工程接入很直接，可复用 GeoNet 15 分钟窗口模型和 RINEX3 long filename 解析。
  - 因区域地震收益有限，优先级低于 Rénag/FReDNet；加勒比站点可与 EarthScope/COCONet 去重后评估。

### Taiwan GDMS / CWA / IES

- 需要确认账号、下载窗口限制、站点覆盖和真实 RINEX 采样率。
- 必须先下载样本检查 header 中的 `INTERVAL` 是否为 1 秒。
- 2026-05-08 重新核实：
  - GDMS GNSS 下载页面要求登录。
  - GDMS 页面限制：GNSS 数据一次选择全测站时，起迄时间不得超过 7 天；外单位 GNSS_IES 和 GNSS_ETEC 只提供当前日期前 30 日数据；其余历史站下载需向 CWA 申请。
  - TGM 页面说明 IES Data Download 只提供 IES 维护台站且超过 6 个月的数据，RINEX 下载支持批量站点和时间范围。
  - TGM/GDMS 页面未直接确认公开匿名 API、许可证和 1 Hz RINEX header。
- 当前判断：
  - 台湾强震和台站密度都值得保留为目标区域。
  - 但不应在未拿到账号和样本前写自动下载器。
  - 下一步应人工登录/申请，下载一个台站一天样本，确认 `INTERVAL=1`、文件命名、批量请求 URL、引用/许可证，再决定是否接入。

## 参考链接

- GeoNet geodetic data: https://www.geonet.org.nz/data/types/geodetic
- GeoNet AWS open data: https://www.geonet.org.nz/data/access/aws
- GeoNet event high-rate GNSS README: https://geonet-open-data.s3.amazonaws.com/gnss/event.highrate/README.gnsshighrate
- GeoNet event high-rate 1 Hz RINEX listing: https://geonet-open-data.s3.amazonaws.com/?list-type=2&prefix=gnss/event.highrate/1hz/rinex/&delimiter=/
- EarthScope NOTA: https://www.earthscope.org/nota/
- EarthScope/GAGE GPS/GNSS data: https://www.unavco.org/data/gps-gnss/gps-gnss.html
- EarthScope/GAGE file server layout: https://www.unavco.org/data/gps-gnss/file-server/file-server.html
- EarthScope/GAGE file server access examples: https://www.unavco.org/data/gps-gnss/file-server/file-server-access-examples.html
- EarthScope/GAGE Web Services spec: https://web-services.unavco.org/spec
- Geoscience Australia GNSS data: https://data.gnss.ga.gov.au/docs/home/gnss-data.html
- Geoscience Australia RINEX API: https://data.gnss.ga.gov.au/docs/rinex-file-query/v1.0/web-api-access.html
- CSN Chile data policy: https://www.csn.uchile.cl/centro-sismologico-nacional/politica-datos/
- NASA CDDIS high-rate GNSS: https://www.earthdata.nasa.gov/data/space-geodesy-techniques/gnss/high-rate-sub-hourly-data-product
- GSI GEONET technical report: https://www.gsi.go.jp/ENGLISH/geonet_technical_report.html
- GSI GEONET data overview: https://www.gsi.go.jp/eiseisokuchi/eiseisokuchi41012.html
- GSI 1-second future dataset archive: https://go.gnss.go.jp/mirai/miraiarchive/
- GSI terms / disclaimer: https://go.gnss.go.jp/terms/disclaimer.html
- JSURVEY 1-second RINEX/BINEX: https://jsurvey.jp/eng-data_rinex-1sec.htm
- FReDNet RINEX data: https://frednet.crs.ogs.it/en/dati-rinex/
- EPOS GNSS Data Gateway: https://gnssdata-epos.oca.eu/
- EPOS GLASS high-rate API example: https://gnssdata-epos.oca.eu/GlassFramework/webresources/files/highrate/station-marker/CASC00PRT/json
- Rénag data access: https://renag.resif.fr/english-technical-center/data-access/
- Rénag 1s RINEX3 directory: https://renag.resif.fr/pub/rinex3_1s/
- NSGI RINEX data: https://www.nsgi.nl/referentiepunten-en-gnss-data/gnss-data/rinex-data
- NSGI highrate directory: https://gnss-data.kadaster.nl/data/highrate/
- Taiwan GDMS GNSS data download: https://gdms.cwa.gov.tw/GNSS_data_download.php
- Taiwan Geodetic Model GNSS data: https://tgm.earth.sinica.edu.tw/?page_id=763
