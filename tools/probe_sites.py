# -*- coding: utf-8 -*-
"""
订阅源站点存活探测 + dead_sites 巡检
=====================================

单次探测:
  python probe_sites.py mirror/anaer_meow.json
  python probe_sites.py mirror/anaer_meow.json 永夜星河
      探测指定源里每个接口/正则类站点(type 0/1)按 mac cms 接口做真实搜索探测,
      判定 存活/空结果/非JSON响应/失活, 并给出失败原因与耗时。
      同时记录到 probe_history.json，追踪连续失败天数。

复活扫描:
  python probe_sites.py --revive dead_sites.json [主源JSON] [关键词]
      对死站名单做复活扫描: 从主源反查站点后逐个探活,
      输出「复活候选」名单; 移回主池前需人工复核并登记台账。

候选报告:
  python probe_sites.py --report
      不探测，仅基于历史记录输出候选 dead_sites 清单（连续 7 天失败）。
      输出候选下架 + 候选恢复，供人工确认。

查看历史:
  python probe_sites.py --history

只读探测, 不修改任何源文件（probe_history.json 除外）。
"""
import json, os, sys, time, urllib.parse, datetime
import concurrent.futures as futures

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import requests
except ImportError:
    requests = None
    import urllib.request, urllib.error

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
TIMEOUT = 8
KEYWORD = "庆余年"

# ---- dead_sites 巡检配置 ----
CONSECUTIVE_DAYS = 7  # 连续失败天数阈值

# 路径推断（脚本在 tools/ 下，源池在上一级）
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_SUBS_REPO = os.path.dirname(_TOOLS_DIR)
HISTORY_FILE = os.path.join(_TOOLS_DIR, "probe_history.json")
DEAD_SITES_FILE = os.path.join(_SUBS_REPO, "dead_sites.json")


def cut(text, width):
    """按字符安全截断, 超宽补省略号, 避免切断 emoji/多字节字符"""
    text = str(text)
    return text if len(text) <= width else text[: width - 1] + "…"


def http_get(url, timeout=TIMEOUT):
    """返回 (status, text, elapsed_ms); 网络异常抛给上层"""
    t0 = time.time()
    if requests:
        r = requests.get(url, headers=UA, timeout=timeout)
        return r.status_code, r.text, int((time.time() - t0) * 1000)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, raw, int((time.time() - t0) * 1000)


def probe(site):
    """返回 (name, verdict, elapsed_ms, url)
    verdict: ALIVE(N) / EMPTY / ALIVE_NONJSON / DEAD(原因) / NO_API"""
    api = (site.get("api") or site.get("url") or "").strip()
    name = site.get("name", "?")
    if not api:
        return name, "NO_API", 0, ""
    base = api if api.endswith(("?", "&")) else api + ("&" if "?" in api else "?")
    tried, reasons = [], []
    t0 = time.time()
    for ac in ("videolist", "list"):
        url = "%sac=%s&wd=%s" % (base, ac, urllib.parse.quote(KEYWORD))
        tried.append(url)
        try:
            st, txt, ms = http_get(url)
        except Exception as e:
            code = getattr(e, "code", None)
            reasons.append(("HTTP %s" % code) if code else type(e).__name__)
            continue
        if st != 200:
            reasons.append("HTTP %d" % st)
            continue
        try:
            d = json.loads(txt)
        except Exception:
            # 有些站返回 XML / 登录页 / 非 JSON
            return name, "ALIVE_NONJSON", ms, url
        lst = d.get("list") or d.get("data") or []
        if isinstance(lst, dict):
            lst = lst.get("list") or []
        return name, ("ALIVE(%d)" % len(lst)) if lst else "EMPTY", ms, url
    elapsed = int((time.time() - t0) * 1000)
    reason = "; ".join(reasons) if reasons else "未尝试任何请求"
    return name, "DEAD(%s)" % cut(reason, 90), elapsed, tried[0] if tried else api


def load(path_or_url):
    if path_or_url.startswith("http"):
        try:
            st, txt, _ = http_get(path_or_url, 20)
        except Exception as e:
            code = getattr(e, "code", None)
            raise SystemExit("读取源失败: %s @ %s\n(检查 URL 是否正确、站点是否存活)"
                             % (("HTTP %s" % code) if code else type(e).__name__, path_or_url))
        if st != 200:
            raise SystemExit("读取源失败: HTTP %d @ %s\n响应片段: %s"
                             % (st, path_or_url, cut(txt, 120)))
        try:
            return json.loads(txt)
        except Exception as e:
            raise SystemExit("源不是合法 JSON: %s (%s)\n响应片段: %s"
                             % (path_or_url, e, cut(txt, 120)))
    try:
        raw = open(path_or_url, "rb").read().decode("utf-8-sig", errors="replace")
        return json.loads(raw)
    except OSError as e:
        raise SystemExit("无法读取本地文件: %s (%s)" % (path_or_url, e))
    except Exception as e:
        raise SystemExit("本地源 JSON 解析失败: %s (%s)" % (path_or_url, e))


# ============================================================
# 历史记录管理
# ============================================================

def load_history():
    """加载历史探测记录。"""
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_history(history):
    """保存历史探测记录。"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_dead_keys():
    """加载当前已确认的 dead_sites keys。"""
    if not os.path.exists(DEAD_SITES_FILE):
        return set()
    with open(DEAD_SITES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("keys", []))


def update_history(results, history):
    """更新历史记录。results = [(site, verdict, ms, url), ...]"""
    today = datetime.date.today().isoformat()
    dead_keys_existing = load_dead_keys()

    for site, verdict, ms, url in results:
        key = site.get("key", "")
        if not key:
            continue

        is_alive = verdict.startswith("ALIVE") or verdict == "EMPTY"

        if key not in history:
            history[key] = {
                "name": site.get("name", ""),
                "api": site.get("api", ""),
                "fail_dates": [],
                "last_verdict": "",
                "last_check": "",
            }

        entry = history[key]
        entry["name"] = site.get("name", "")
        entry["api"] = site.get("api", "")
        entry["last_verdict"] = verdict
        entry["last_check"] = today

        if not is_alive:
            # 今天失败了
            fail_dates = entry.get("fail_dates", [])
            if today not in fail_dates:
                fail_dates.append(today)
            entry["fail_dates"] = fail_dates[-CONSECUTIVE_DAYS:]
        else:
            # 今天活了，清空连续失败记录
            entry["fail_dates"] = []

        entry["in_dead_sites"] = key in dead_keys_existing

    save_history(history)
    return history


def generate_report(history=None):
    """生成候选 dead_sites 清单（不探测）。"""
    if history is None:
        history = load_history()
    dead_keys_existing = load_dead_keys()

    candidates = []
    for key, entry in history.items():
        fail_count = len(entry.get("fail_dates", []))
        if fail_count >= CONSECUTIVE_DAYS and key not in dead_keys_existing:
            candidates.append({
                "key": key,
                "name": entry.get("name", ""),
                "api": entry.get("api", ""),
                "consecutive_fails": fail_count,
                "fail_dates": entry.get("fail_dates", []),
                "last_verdict": entry.get("last_verdict", ""),
            })

    recovered = []
    for key in dead_keys_existing:
        if key in history:
            entry = history[key]
            if not entry.get("fail_dates"):
                # 最近一次探测成功了（fail_dates 被清空）
                recovered.append({
                    "key": key,
                    "name": entry.get("name", ""),
                    "last_verdict": entry.get("last_verdict", ""),
                })

    return candidates, recovered


# ============================================================
# 命令处理
# ============================================================

def run_revive(dead_path, args):
    """死站复活扫描: args = [dead_sites.json, 主源JSON(可选), 关键词(可选)]"""
    global KEYWORD
    meow_path = args[1] if len(args) > 1 else "mirror/anaer_meow.json"
    if len(args) > 2:
        KEYWORD = args[2]
    dead = load(dead_path)
    keys = [k for k in dead.get("keys", []) if isinstance(k, str)]
    meow = {s.get("key"): s for s in load(meow_path).get("sites", [])}
    targets = [meow[k] for k in keys if k in meow]
    missing = [k for k in keys if k not in meow]
    print("复活扫描: 死站名单 %d 个, 主源(%s)反查到 %d 个%s | 关键词 %s"
          % (len(keys), os.path.basename(meow_path), len(targets),
             (" | 未找到: %s" % ", ".join(missing)) if missing else "", KEYWORD))
    print("=" * 78)
    revived = []
    with futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(probe, s): s for s in targets}
        for fu in futures.as_completed(futs):
            try:
                name, verdict, ms, url = fu.result()
            except Exception:
                name, verdict, ms, url = futs[fu].get("name", "?"), "ERR", 0, ""
            print("  [%6dms] %s  %s" % (ms, cut(name, 24), cut(verdict, 60)))
            if verdict.startswith("ALIVE("):
                revived.append(name)
    print("\n复活候选 %d 个（建议连续 2 轮探测确认后再移回主池, 并登记 excluded_sites.json）"
          % len(revived))
    for name in sorted(revived):
        print("  - %s" % name)
    return 0


def cmd_report():
    """输出候选清单（不探测）。"""
    history = load_history()
    candidates, recovered = generate_report(history)

    print("=== dead_sites 候选清单 ===")
    print("判定标准: 连续 %d 天探测失败 (API+网络双失败)" % CONSECUTIVE_DAYS)
    print()
    if candidates:
        print("候选下架 (%d):" % len(candidates))
        for c in candidates:
            print("  %s  %s  (连续失败 %d 天)  %s" % (
                c["key"][:12], cut(c["name"], 20), c["consecutive_fails"],
                cut(c["last_verdict"], 50)
            ))
        print("\n需人工确认后更新 dead_sites.json")
    else:
        print("无新增候选下架")

    print()
    if recovered:
        print("候选恢复 (%d):" % len(recovered))
        for r in recovered:
            print("  %s  %s  %s" % (r["key"][:12], cut(r["name"], 20), r.get("last_verdict", "")))
        print("\n可从 dead_sites.json 移除")
    else:
        print("无候选恢复")

    dead_count = len(load_dead_keys())
    print()
    print("当前 dead_sites.json: %d 个" % dead_count)


def cmd_history():
    """查看历史记录。"""
    history = load_history()
    if not history:
        print("无历史记录（需先运行探测生成）")
        return

    print("=== 探测历史 ===")
    print("站点数: %d" % len(history))
    print()

    entries = []
    for key, entry in history.items():
        fail_count = len(entry.get("fail_dates", []))
        entries.append((fail_count, key, entry))

    entries.sort(key=lambda x: -x[0])

    print("%-14s %-20s %-6s %-12s %s" % ("key", "name", "fails", "last_check", "last_verdict"))
    print("-" * 90)
    for fail_count, key, entry in entries:
        print("%-14s %-20s %-6d %-12s %s" % (
            key[:12],
            cut(entry.get("name", ""), 20),
            fail_count,
            entry.get("last_check", ""),
            cut(entry.get("last_verdict", ""), 40),
        ))


def main():
    args = sys.argv[1:]

    # --report: 只输出候选清单（不探测）
    if args and args[0] == "--report":
        cmd_report()
        return

    # --history: 查看历史记录
    if args and args[0] == "--history":
        cmd_history()
        return

    revive = bool(args) and args[0] == "--revive"
    if revive:
        args = args[1:]
    src = args[0] if args else ""
    if not src:
        print(__doc__)
        return
    global KEYWORD
    if not revive and len(args) > 1:
        KEYWORD = args[1]
    if revive:
        return run_revive(src, args)

    # 正常探测模式
    d = load(src)
    sites = d.get("sites", [])
    t1 = [s for s in sites if str(s.get("type")) in ("1", "0") and s.get("searchable", 1) == 1]
    print("源: %s | 总站点 %d | 待探测(接口/正则且可搜) %d | 关键词 %s"
          % (os.path.basename(src), len(sites), len(t1), KEYWORD))
    print("=" * 78)
    res = {"ALIVE": [], "EMPTY": [], "NONJSON": [], "DEAD": [], "OTHER": []}
    history = load_history()
    probe_results = []  # 用于更新历史
    with futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(probe, s): s for s in t1}
        for fu in futures.as_completed(futs):
            try:
                name, verdict, ms, url = fu.result()
            except Exception as e:
                name, verdict, ms, url = futs[fu].get("name", "?"), "ERR(%s)" % type(e).__name__, 0, ""
            # 记录用于历史更新
            site = futs[fu]
            probe_results.append((site, verdict, ms, url))

            if verdict.startswith("ALIVE("):
                res["ALIVE"].append((ms, name, verdict, url))
            elif verdict == "EMPTY":
                res["EMPTY"].append((ms, name, verdict, url))
            elif verdict == "ALIVE_NONJSON":
                res["NONJSON"].append((ms, name, verdict, url))
            elif verdict.startswith("DEAD"):
                res["DEAD"].append((ms, name, verdict, url))
            else:
                res["OTHER"].append((ms, name, verdict, url))
    for k in ("ALIVE", "EMPTY", "NONJSON", "OTHER", "DEAD"):
        rows = sorted(res[k]) if k == "ALIVE" else res[k]
        print("\n### %s  (%d)" % (k, len(rows)))
        for ms, name, verdict, url in rows:
            print("  [%6dms] %s  %s" % (ms, cut(name, 24), cut(verdict, 60)))
            if k == "DEAD":
                print("           %s" % cut(url, 90))
    print("\n汇总: 可出片 %d / 空结果 %d / 非JSON响应 %d / 失活 %d / 其他 %d"
          % (len(res["ALIVE"]), len(res["EMPTY"]), len(res["NONJSON"]),
             len(res["DEAD"]), len(res["OTHER"])))

    # 更新历史记录
    history = update_history(probe_results, history)

    # 输出候选清单
    candidates, recovered = generate_report(history)
    if candidates:
        print("\n--- 候选 dead_sites (连续 %d 天失败) ---" % CONSECUTIVE_DAYS)
        for c in candidates:
            print("  %s  %s  fails=%d  %s" % (
                c["key"][:12], cut(c["name"], 20), c["consecutive_fails"], cut(c["last_verdict"], 50)
            ))
        print("  共 %d 个候选，需人工确认后更新 dead_sites.json" % len(candidates))
    if recovered:
        print("\n--- 已恢复（在 dead_sites 中但探测成功）---")
        for r in recovered:
            print("  %s  %s  %s" % (r["key"][:12], cut(r["name"], 20), r.get("last_verdict", "")))
        print("  共 %d 个已恢复，可从 dead_sites.json 移除" % len(recovered))


if __name__ == "__main__":
    main()
