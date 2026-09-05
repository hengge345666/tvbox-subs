# -*- coding: utf-8 -*-
"""
订阅源站点存活探测（P2）
用法: python probe_sites.py <源JSON的URL或本地路径> [关键词]
输出: 每个接口/正则类站点(type 0/1)按 mac cms 接口做真实搜索探测,
      判定 存活/空结果/非JSON响应/失活, 并给出失败原因与耗时。
只读探测, 不修改任何源文件。
"""
import json, os, sys, time, urllib.parse
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


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    if not src:
        print(__doc__)
        return
    global KEYWORD
    if len(sys.argv) > 2:
        KEYWORD = sys.argv[2]
    d = load(src)
    sites = d.get("sites", [])
    t1 = [s for s in sites if str(s.get("type")) in ("1", "0") and s.get("searchable", 1) == 1]
    print("源: %s | 总站点 %d | 待探测(接口/正则且可搜) %d | 关键词 %s"
          % (os.path.basename(src), len(sites), len(t1), KEYWORD))
    print("=" * 78)
    res = {"ALIVE": [], "EMPTY": [], "NONJSON": [], "DEAD": [], "OTHER": []}
    with futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(probe, s): s for s in t1}
        for fu in futures.as_completed(futs):
            try:
                name, verdict, ms, url = fu.result()
            except Exception as e:
                name, verdict, ms, url = futs[fu].get("name", "?"), "ERR(%s)" % type(e).__name__, 0, ""
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


if __name__ == "__main__":
    main()
