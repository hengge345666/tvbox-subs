---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: 'd868d7ee-c3d3-4f1e-bfb9-6408f72298d2'
  PropagateID: 'd868d7ee-c3d3-4f1e-bfb9-6408f72298d2'
  ReservedCode1: '5cf4ff22-058c-443f-aa71-eb7a1780d4bc'
  ReservedCode2: '5cf4ff22-058c-443f-aa71-eb7a1780d4bc'
---

# tvbox-subs

TVBox 订阅聚合与数据源维护仓库。本仓库作为远程配置源，供 TVBox 类应用热更拉取：
订阅索引（`subs.json`）、自更新清单（`version.json`）、广告域名黑名单（`ads.json`）、
失效站点名单（`dead_sites.json`），以及若干镜像化的第三方配置（`mirror/`）。

## 订阅入口

`subs.json` 精选 17 条线路（每条上游唯一、全部 https、CI 实时校验可达）：

- **直播**：自建 tang_live（稳定精选+日更层+IPV6）、南风+咪咕、全部直播合集
- **点播大库**：高天流云 JS 库(297源)、yw88075 HTTP 库(211源)、qist 合集(151源)、C88(92源)、教主(93源)
- **轻量/精简**：A站(24源)、Tomorrow(47源)、饭太硬(49源)、FongMI(33源)、noimank(64源)
- **聚合/其他**：喵站主力配置、老刘备、香雅情XYQ、无意wya6

## 文件地图

| 文件 | 用途 | 消费方 |
|---|---|---|
| `subs.json` | 订阅接口索引（17 条，上游唯一化） | TVBox 应用「订阅」入口 |
| `version.json` | App 自更新 OTA 清单（版本号 / APK 地址 / 更新日志） | TVBox 应用检查更新 |
| `ads.json` | 广告域名黑名单（含 note / updated 元数据） | TVBox 应用热更 |
| `dead_sites.json` | 已探测确认失效的源站 key，供首日跳过 | TVBox 应用热更 |
| `mirror/tang_live.json` | 自建直播总入口（精选 + 3 家日更上游 + Raycorn IPV6） | `subs.json` 首条 |
| `mirror/anaer_meow.json` | 喵站主力自用配置（源 + 解析/播放/广告/直播/壁纸） | `subs.json` |
| `mirror/live.m3u` | 全部直播合集（喵站+南风+咪咕，实测存活） | `subs.json` + `anaer_meow.json` |
| `mirror/migu_live.m3u` | 咪咕直播镜像（169 频道） | `autoiptv_live.json` |
| `mirror/{c88_box,fongmi0827,gao_js,hackyjso_jzy,qist_jsm,qist_fty,yw88075_js}.json` | 第三方点播配置镜像 | `subs.json` |
| `mirror/autoiptv_live.json` | 南风直播 + 咪咕组合入口 | `subs.json` |
| `iptv/` | 自维护直播清单（精选 m3u/txt、full、EPG） | `tang_live.json` 等 |
| `tools/probe_sites.py` | MacCMS 源站存活探测脚本（并发 12、只读） | 维护工具 |
| `tools/excluded_sites.json` | 排除决策审计台账（死站/慢站/成人站/恢复记录） | 维护记录 |
| `tools/_to_exclude.json` | 拟排除站点草稿（与 `excluded_sites.json` 同步） | 维护记录 |
| `tools/validate.py` | 仓库质量校验（JSON 语法 / key 唯一 / dead_sites 一致性 / mirror 零引用 / 订阅去重） | CI 与本地自检 |
| `tools/check_urls.py` | 订阅与更新链路可达性检查（https 强制 + 外链 HEAD 探测） | CI 与本地自检 |
| `reports/` | 周期探测报告（每周自动生成，保留历史） | GitHub Actions |

## 更新流程

1. 上游配置更新后，镜像文件放 `mirror/`（保持文件名不变）。
2. 跑 `tools/probe_sites.py <源JSON> [关键词]` 探测站点存活（只读）；每周一 04:00（北京时间）GitHub Actions 也会自动跑一轮并回写报告到 `reports/`。
3. 依探测结果更新 `dead_sites.json`，并在 `tools/excluded_sites.json` 登记决策；`--revive` 可对死站名单做复活扫描（`python tools/probe_sites.py --revive dead_sites.json`）。
4. 本地跑 `python tools/validate.py` 自检：JSON 与 key 唯一性、mirror 零引用（防死重堆积）、subs.json 上游去重。
5. 提交推送；CI 会自动重跑同样的校验，并对 `subs.json` / `version.json` 的全部外链做可达性检查。

## 手动备用源

以下源因走 HTTP 明文传输（配置可被链路篡改，且 CI 强制 https），不进 `subs.json` 默认订阅，
仅作手动添加备用：

- 饭太硬·官方接口：`http://www.饭太硬.net/tv`
- 俊佬·jundie线路：`http://home.jundie.top:81/top98.json`
- 巧计·pandown线路：`http://pandown.pro/tvbox/tvbox.json`
- 影探·lyyytv线路：`http://www.lyyytv.cn/yt/yt.json`
- 肥猫·多源聚合：`http://肥猫.net/`
- 摸鱼·4K资源：`http://我不是.摸鱼儿.top`
- 王二小放牛娃·多源聚合：`http://tvbox.王二小放牛娃.top`
- 南风·XC源（点播）：`https://gh-proxy.com/https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json`

## 整合记录（2026-09-25）

- 修复：`hackyjso_jzy.json`（BOM/缺引号/GBK 双重编码损坏，机械修复 19 轮）、`yw88075_js.json`（JSON 内注释行）、`gao_js.json` 重复 key
- 断链清理：移除指向已不存在 `sat_live.json` 的订阅条目、404 的道长 GitLab 线路
- 去重：删除与 `gao_js.json` 完全同源的 `js.json`、md5 相同的 `anaer_live_iptvfirst.json`、零引用文件 ×6（anaer_iptv / anaer_iptv_cdn / anaer_live / guovin_live / live.txt / meow_live.txt）、空壳包装文件 ×2（live.json / raycorn_live.json，Raycorn 折入 tang_live）、qist_lite
- 订阅从 32 条精选至 17 条（每组重复上游保留验活最优一条）
- 防复发：`validate.py` 新增 mirror 零引用检测与订阅上游去重检测

## 源池健康

<!-- health:start 由 Weekly Probe 工作流维护, 手动编辑会被覆盖 -->

等待首轮定时探测后自动填充：各镜像可出片站点数 / 失活数 / 探测时间。

<!-- health:end -->

## 致谢与来源声明

本仓库镜像并聚合了以下第三方配置，版权归各自作者所有，仅作个人收藏与加速分发之用：

- [anaer/Meow](https://github.com/anaer/sub) — 主力配置与直播清单
- [hackyjso](https://github.com/hackyjso/jso) — jzy 爬虫配置
- [yw88075](https://github.com/yw88075/tvbox) — JS 大库镜像
- [cluntop/tvbox](https://github.com/cluntop/tvbox) — C88 聚合 / A 站轻量源
- [tushen6/Tomorrow](https://github.com/tushen6/Tomorrow) — 采集源
- [gaotianliuyun/gao](https://github.com/gaotianliuyun/gao) — drpy2 运行库与部分 JS
- [qist](https://github.com/qist/tvbox) — OK影视合集与饭太硬镜像
- [RaycornM/TVbox-IPTV](https://github.com/RaycornM/TVbox-IPTV) — IPV6 直播
- [yoursmile66/TVBox](https://github.com/yoursmile66/TVBox) — 南风直播

若你是上述作者且不希望被镜像，请提 issue，我会及时移除。

## 许可

本仓库自身代码与整理内容以 [MIT](LICENSE) 释出；镜像的第三方配置遵循其各自原始许可。

> AI生成
