# USGS 实时监控命令说明

本文档记录 `gnss-eq watch-usgs` 的常用命令。这个命令只负责监控、告警和记录 USGS 新地震事件；不会自动下载 GNSS 数据，也不会自动运行 PRIDE/workflow。

## 1. 快速检查

只轮询一次，使用默认设置：

```bash
gnss-eq watch-usgs --once
```

默认含义：

- 监控范围：美洲 + 新西兰/Kermadec，等价于 `--scope americas,nz`
- 最小震级：M6.0，等价于 `--min-magnitude 6`
- 首次启动回看：24 小时，等价于 `--lookback-minutes 1440`
- 状态数据库：`data/live/usgs_watcher.sqlite`

如果输出类似：

```text
POLL    OK    ...    mode=overlap window=... fetched=0 new=0
```

表示 USGS 查询成功，但本轮没有新的告警事件。

## 2. 测试能否查到历史事件

调试时建议降低震级并强制回看 7 天：

```bash
gnss-eq watch-usgs --once --ignore-state --lookback-minutes 10080 --min-magnitude 4.0
```

重点看 `POLL` 行：

```text
mode=lookback window=... fetched=49 new=0
```

字段含义：

- `mode=lookback`：本轮按 `--lookback-minutes` 回看。
- `window=...`：实际查询的 UTC 时间窗口。
- `fetched=49`：USGS 返回了 49 个符合范围和震级条件的事件。
- `new=0`：这些事件已经在状态数据库里记录过，所以不会重复输出 `EVENT`。

如果想重新看到 `EVENT` 行，用一个新的临时数据库：

```bash
gnss-eq watch-usgs --once \
  --state-db /tmp/usgs-watch-test.sqlite \
  --ignore-state \
  --lookback-minutes 10080 \
  --min-magnitude 4.0
```

再次运行同一条命令时，通常会变成 `new=0`，这是去重生效的表现。

## 3. 正式长期运行

推荐正式监控 M6+：

```bash
gnss-eq watch-usgs --interval 300 --min-magnitude 6 --scope americas,nz
```

含义：

- 每 300 秒查询一次 USGS。
- 只监控美洲 + 新西兰/Kermadec。
- 只告警 M6.0 及以上事件。
- 使用状态数据库去重，避免重复告警同一个 `event_id`。

如果在终端里长期运行，可以用 `tmux`：

```bash
tmux new -s usgs-watch
gnss-eq watch-usgs --interval 300 --min-magnitude 6 --scope americas,nz
```

停止时按：

```text
Ctrl+C
```

## 4. 保存日志

TSV 日志：

```bash
gnss-eq watch-usgs --interval 300 --min-magnitude 6 | tee -a usgs-watch.tsv
```

JSONL 日志，适合脚本或大模型读取：

```bash
gnss-eq watch-usgs --interval 300 --min-magnitude 6 --format jsonl | tee -a usgs-watch.jsonl
```

只测试一次 JSONL 输出：

```bash
gnss-eq watch-usgs --once --ignore-state --lookback-minutes 10080 --min-magnitude 4.0 --format jsonl
```

## 5. 监控范围

默认：

```bash
--scope americas,nz
```

只监控美洲：

```bash
gnss-eq watch-usgs --once --scope americas
```

只监控新西兰/Kermadec：

```bash
gnss-eq watch-usgs --once --scope nz
```

## 6. 常用参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--once` | 关闭 | 只轮询一次，不进入循环。适合测试。 |
| `--interval` | `300` | 循环模式下每隔多少秒查一次。 |
| `--scope` | `americas,nz` | 监控范围：`americas`、`nz` 或 `americas,nz`。 |
| `--min-magnitude` | `6.0` | 最小震级。测试可用 `4.0`，正式建议 `6.0`。 |
| `--lookback-minutes` | `1440` | 没有历史状态时，首次回看多少分钟。 |
| `--overlap-minutes` | `30` | 有历史状态时，从上次完成时间往前重叠多少分钟再查。 |
| `--ignore-state` | 关闭 | 本轮忽略上次完成时间，强制使用 `--lookback-minutes`。适合测试/回补。 |
| `--state-db` | `data/live/usgs_watcher.sqlite` | SQLite 状态数据库路径。 |
| `--format` | `tsv` | 输出格式：`tsv` 或 `jsonl`。 |
| `--timeout` | `30` | 单次 USGS HTTP 请求超时时间，单位秒。 |
| `--limit` | `2000` | 每个 USGS 区域查询最多返回多少事件。 |

## 7. 输出字段解释

TSV 第一行是表头。常见行类型：

- `POLL`：本轮轮询摘要。
- `EVENT`：本轮第一次见到的新事件。
- `ERROR`：本轮请求失败或解析失败。

`POLL` 行中的 `detail` 字段示例：

```text
mode=lookback window=2026-06-21T08:16:03Z..2026-06-28T08:16:03Z urls=4 fetched=49 new=49
```

含义：

- `mode=lookback`：按 `--lookback-minutes` 查询。
- `mode=overlap`：按状态数据库中的上次完成时间查询。
- `urls=4`：内部查询了 4 个 USGS 区域框。
- `fetched=49`：USGS 返回并通过区域过滤的事件数。
- `new=49`：本轮第一次见到、需要告警的事件数。

`EVENT` 行包含：

- `event_id`：USGS 事件 ID。
- `event_time_utc`：地震发生时间。
- `first_seen_utc`：watcher 第一次记录到该事件的时间。
- `magnitude`：震级。
- `latitude` / `longitude` / `depth_km`：震源位置和深度。
- `region`：内部分类，`americas` 或 `new_zealand`。
- `place` / `title`：USGS 地点描述。
- `usgs_url`：USGS 事件页面。
- `detail`：USGS GeoJSON 详情 URL。

## 8. 状态数据库和去重

默认状态数据库：

```text
data/live/usgs_watcher.sqlite
```

它记录：

- 已经见过的 `event_id`。
- 每个事件第一次见到和最后一次见到的时间。
- 上次轮询完成时间。
- 每轮轮询状态。

所以：

```text
fetched=49 new=0
```

不是错误，而是表示 USGS 查到了 49 个事件，但它们都已经记录过，不再重复告警。

如果只是测试，不想影响默认状态数据库，用临时库：

```bash
gnss-eq watch-usgs --once --state-db /tmp/usgs-watch-test.sqlite --ignore-state --lookback-minutes 10080 --min-magnitude 4.0
```

如果确实要重置默认状态，可以删除：

```bash
rm -f data/live/usgs_watcher.sqlite
```

注意：删除默认状态后，之前见过的事件会被当成新事件重新告警。

## 9. 推荐命令组合

### 日常正式监控

```bash
gnss-eq watch-usgs --interval 300 --min-magnitude 6 --scope americas,nz
```

### 查看最近 7 天低震级样例

```bash
gnss-eq watch-usgs --once --ignore-state --lookback-minutes 10080 --min-magnitude 4.0
```

### 用全新临时库验证 EVENT 输出

```bash
gnss-eq watch-usgs --once --state-db /tmp/usgs-watch-test.sqlite --ignore-state --lookback-minutes 10080 --min-magnitude 4.0
```

### 给大模型/脚本读取

```bash
gnss-eq watch-usgs --interval 300 --min-magnitude 6 --format jsonl | tee -a usgs-watch.jsonl
```
