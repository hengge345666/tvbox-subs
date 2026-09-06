# tvbox-subs

TVBox 订阅聚合与数据源维护仓库。本仓库作为远程配置源，供 TVBox 类应用热更拉取：
订阅索引（`subs.json`）、自更新清单（`version.json`）、广告域名黑名单（`ads.json`）、
失效站点名单（`dead_sites.json`），以及若干镜像化的第三方配置（`mirror/`）。

## 文件地图

| 文件 | 用途 | 消费方 |
|---|---|---|
| `subs.json` | 订阅接口索引（7 条，含 gh-proxy 镜像与第三方源） | TVBox 应用「订阅」入口 |
| `version.json` | App 自更新 OTA 清单（版本号 / APK 地址 / 更新日志） | TVBox 应用检查更新 |
| `ads.json` | 91 条广告域名黑名单（含 note / updated 元数据） | TVBox 应用热更 |
| `dead_sites.json` | 24 个已探测确认失效的源站 key，供首日跳过 | TVBox 应用热更 |
| `mirror/anaer_meow.json` | 主力自用配置（77 源 + 解析/播放/广告/直播/壁纸） | `subs.json` 首条指向 |
| `mirror/anaer_live.json` | 直播频道清单（29 组） | 被 `anaer_meow.json` 的 `lives[0]` 引用 |
| `mirror/js.json` | 「hkuc_js 混合大库」（297 源，JS 爬虫为主） | 供外部订阅使用 |
| `mirror/yw88075_js.json` | 「yw88075 HTTP 大库」（211 源） | 供外部订阅使用 |
| `mirror/hackyjso_jzy.json` | 「教主/老牌爬虫」配置（93 源） | 供外部订阅使用 |
| `mirror/anaer_iptv.json` | IPTV 分组配置（18 组） | ⚠️ 仓内零引用，可能被 App 硬编码拉取 |
| `mirror/anaer_iptv_cdn.json` | IPTV 分组配置 CDN 变体（14 组） | ⚠️ 仓内零引用，同上 |
| `mirror/anaer_live_iptvfirst.json` | 直播清单变体（IPTV 优先排序） | ⚠️ 仓内零引用，同上 |
| `tools/probe_sites.py` | MacCMS 源站存活探测脚本（并发 12、只读） | 维护工具 |
| `tools/excluded_sites.json` | 排除决策审计台账（死站/慢站/成人站/恢复记录） | 维护记录 |
| `tools/_to_exclude.json` | 拟排除站点草稿（与 `excluded_sites.json` 同步） | 维护记录 |
| `tools/validate.py` | 仓库质量校验（JSON 语法 / 站点 key 唯一性 / dead_sites 交叉一致性） | CI 与本地自检 |
| `tools/check_urls.py` | 订阅与更新链路可达性检查（https 强制 + 外链 HEAD 探测） | CI 与本地自检 |
| `reports/` | 周期探测报告（每周自动生成，保留历史） | GitHub Actions |

## 更新流程

1. 上游配置更新后，镜像文件放 `mirror/`（保持文件名不变）。
2. 跑 `tools/probe_sites.py <源JSON> [关键词]` 探测站点存活（只读）；每周一 04:00（北京时间）GitHub Actions 也会自动跑一轮并回写报告到 `reports/`。
3. 依探测结果更新 `dead_sites.json`，并在 `tools/excluded_sites.json` 登记决策；`--revive` 可对死站名单做复活扫描（`python tools/probe_sites.py --revive dead_sites.json`）。
4. 本地跑 `python tools/validate.py` 自检，确认 JSON 与 key 唯一性没问题。
5. 提交推送；CI 会自动重跑同样的校验，并对 `subs.json` / `version.json` 的全部外链做可达性检查。

## 手动备用源

以下源因走 HTTP 明文传输（配置可被链路篡改），已从 `subs.json` 默认订阅中移除，仅作手动添加备用：

- T经典保底：`http://home.jundie.top:81/top98.json`

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

若你是上述作者且不希望被镜像，请提 issue，我会及时移除。

## 许可

本仓库自身代码与整理内容以 [MIT](LICENSE) 释出；镜像的第三方配置遵循其各自原始许可。
