# TVBox 直播源

公开 IPTV 源经「多源聚合 → 测速筛选 → 真播放验证」后生成的播放列表。
生成时间：2026-09-24。

---

## 直接填进 TVBox

### ★ 首选：gh-proxy 加速（与本仓库 `subs.json` 用的一致）

```
https://gh-proxy.com/https://raw.githubusercontent.com/hengge345666/tvbox-subs/main/iptv/live.m3u
```

### 次选：jsDelivr CDN

```
https://cdn.jsdelivr.net/gh/hengge345666/tvbox-subs@main/iptv/live.m3u
```

### GitHub 原始地址

```
https://raw.githubusercontent.com/hengge345666/tvbox-subs/main/iptv/live.m3u
```

> `raw.githubusercontent.com` 在国内经常超时或被重置，三个地址内容完全一致，
> 拉不到就换下一个。本仓库 `subs.json` 里其它源也统一走 `gh-proxy.com`。

### TVBox「直播」入口的 JSON 配置

```
https://gh-proxy.com/https://raw.githubusercontent.com/hengge345666/tvbox-subs/main/iptv/live.json
```

内容形如 `{"lives":[{"name":"精选直播","type":0,"url":".../live.m3u"}]}`，
适合 TVBox 要求 JSON 的版本。

---

## 文件说明

| 文件 | 条数 | 说明 |
|---|---|---|
| `live.m3u` | 13 | **精选版**。每条都用 ffprobe 实际拉流验证过，能解出画面 |
| `live.txt` | 13 | 同上，TXT 格式（部分播放器只认 txt） |
| `full.m3u` | 110 | 全量版。53 个频道，质量参差，未做播放验证 |
| `full.txt` | 110 | 同上，TXT 格式 |
| `epg.gz` | — | 节目单（可选，填了能显示节目预告） |
| `epg.xml` | — | 同上，未压缩 |

---

## 精选版包含哪些频道

| 速率 | 延迟 | 实测 | 频道 |
|---|---|---|---|
| 7.52 MiB/s | 27 ms | h264 1080p | 海南卫视 |
| 5.42 MiB/s | 31 ms | h264 1080p | 浙江卫视 |
| 5.08 MiB/s | 21 ms | h264 1080p | CCTV-13 |
| 4.72 MiB/s | 102 ms | h264 1080p | 内蒙古卫视 |
| 4.59 MiB/s | 79 ms | h264 576p | 河南卫视 |
| 3.97 MiB/s | 48 ms | hevc 4K | 湖南卫视 |
| 2.40 MiB/s | 71 ms | h264 720p | 三沙卫视 |
| 1.59 MiB/s | 715 ms | h264 720p | CCTV-15 |
| 1.55 MiB/s | 43 ms | h264 540p | 黑龙江卫视 |
| 1.42 MiB/s | 604 ms | h264 1080p | 大湾区卫视 |
| 1.08 MiB/s | 312 ms | h264 1080p | 新疆卫视 |

**兼容性提醒**

- 湖南卫视是 **HEVC 4K**，老电视盒解不了会黑屏，可删除该条。
- CCTV-15、大湾区卫视是**境外**线路，延迟 600+ ms。
- 河南卫视 URL 带 `key`/`authid` 鉴权参数，**有过期风险**。

---

## 说明

- 本仓库只做源聚合与测速，**不托管、不提供任何直播源**，源均来自第三方公开项目。
- 播放列表仅供测试研究，请勿用于商业传播。请只观看自己有权观看的内容。
- 源会失效，这是公开源的常态。失效后需要重新生成。
