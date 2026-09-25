# -*- coding: utf-8 -*-
"""全量直播源倍速扫描: mirror/live.m3u + 日更上游 -> scan_result.json
每条: 拉m3u8+连续3分片, 记录 kbps/倍速/TTFB
"""
import re, time, ssl, sys, json, socket
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

socket.setdefaulttimeout(10)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 9) MXPlayer/1.20"}

def fetch(url, timeout=10, max_bytes=1<<20):
    req = urllib.request.Request(url, headers=UA)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx if url.startswith("https") else None) as r:
        body = r.read(65536); ttfb = time.time() - t0
        while len(body) < max_bytes:
            c = r.read(262144)
            if not c: break
            body += c
    return body, ttfb, time.time() - t0

def probe(url):
    """返回 dict: kbps, ratio, ttfb, dead(bool), reason"""
    out = {"url": url, "kbps": 0, "ratio": 0, "ttfb": 0, "dead": True, "reason": ""}
    try:
        body, ttfb, _ = fetch(url)
        text = body.decode("utf-8", "replace")
        if "#EXTINF" not in text and "#EXT-X" not in text:
            m = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', text)
            if m:
                url = m.group(0)
                body, ttfb, _ = fetch(url)
                text = body.decode("utf-8", "replace")
            else:
                out["reason"] = "非m3u8"; return out
        durs = [float(x) for x in re.findall(r"#EXTINF:([\d.]+)", text)]
        lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("#")]
        if not lines or not durs:
            out["reason"] = "空列表"; return out
        segs, sd = lines[-3:], durs[-3:]
        base = url.rsplit("/", 1)[0] + "/"
        tb, tt, td = 0, 0.0, 0.0
        for s, d in zip(segs, sd):
            su = s if s.startswith("http") else base + s
            b, _, dt = fetch(su, timeout=15)
            tb += len(b); tt += dt; td += d
        if tt <= 0 or td <= 0:
            out["reason"] = "零耗时"; return out
        out.update(kbps=tb*8/tt/1000, ratio=round(td/tt, 2), ttfb=round(ttfb, 3),
                   dead=False, reason="ok")
        return out
    except Exception as e:
        out["reason"] = f"{type(e).__name__}:{str(e)[:40]}"
        return out

def parse_list(text):
    """m3u/txt -> [(name, url)], 同行多URL取第一个"""
    out = []
    for line in text.split("\n"):
        ln = line.strip()
        if not ln or ln.startswith("#EXTM3U"): continue
        if ln.startswith("#EXTINF"):
            nm = ln.split(",")[-1].strip()
            out.append(["__NAME__", nm]); continue
        urls = re.findall(r'https?://[^\s;,#]+', ln)
        if not urls: continue
        name = ""
        if out and out[-1][0] == "__NAME__":
            name = out[-1][1]; out[-1] = ["KEEP", name, urls]
        else:
            m = re.match(r'^(.*?),https?://', ln)
            name = m.group(1).strip() if m and m.group(1).strip() else "?"
            out.append(["KEEP", name, urls])
    return [(n, us) for t, n, *rest in [x if len(x) == 3 else ["",""] for x in out] for us in [rest] if t == "KEEP"]

def main():
    targets = []  # (group, name, url)
    # 1) mirror/live.m3u (m3u格式)
    t = open(r"mirror/live.m3u", encoding="utf-8").read()
    for nm, u in re.findall(r'#EXTINF:[^\n]*,(.+)\n(\S+)', t):
        targets.append(("all", nm.strip(), u.strip()))
    # 2) 日更上游
    ups = [("migu", "https://gh-proxy.com/https://raw.githubusercontent.com/Supprise0901/TVBox_live/main/live.txt"),
           ("cnip", "https://gh-proxy.com/https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8"),
           ("vbsk", "https://gh-proxy.com/https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt")]
    for label, u in ups:
        try:
            body, _, _ = fetch(u, timeout=20, max_bytes=8<<20)
            txt = body.decode("utf-8", "replace")
            for nm, us in parse_list(txt):
                if us: targets.append((label, nm, us[0]))
        except Exception as e:
            print(f"上游 {label} 拉取失败: {e}", flush=True)

    print(f"总目标: {len(targets)} 条", flush=True)
    results = []
    done = [0]
    def work(t_):
        grp, nm, u = t_
        r = probe(u)
        r.update(group=grp, name=nm)
        done[0] += 1
        if done[0] % 50 == 0: print(f"  进度 {done[0]}/{len(targets)}", flush=True)
        return r
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(work, targets):
            results.append(r)
    json.dump(results, open("scan_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    alive = [r for r in results if not r["dead"]]
    fast = [r for r in alive if r["ratio"] >= 3 and r["ttfb"] < 1]
    print(f"存活 {len(alive)}/{len(results)}  达标(≥3x且TTFB<1s) {len(fast)}", flush=True)
    print("DONE", flush=True)

if __name__ == "__main__":
    main()
