# -*- coding: utf-8 -*-
"""直播流实测: 模拟播放器逐分片拉流, 测实时倍速/首包延迟/稳定性"""
import json, re, time, ssl, sys, urllib.request, urllib.error, socket
from concurrent.futures import ThreadPoolExecutor

socket.setdefaulttimeout(12)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 9) MXPlayer/1.20"}

def fetch(url, timeout=12, max_bytes=None, stop_at=None):
    """GET, 返回 (bytes, ttfb秒, 总耗时秒)"""
    req = urllib.request.Request(url, headers=UA)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx if url.startswith("https") else None) as r:
        body = r.read(65536)
        ttfb = time.time() - t0
        while True:
            if stop_at and time.time() - t0 > stop_at: break
            chunk = r.read(262144)
            if not chunk: break
            body += chunk
            if max_bytes and len(body) >= max_bytes: break
    return body, ttfb, time.time() - t0

def probe_m3u8(url, nseg=3):
    """m3u8: 拉播放列表+连续下载nseg个分片, 返回指标"""
    try:
        body, ttfb, _ = fetch(url, timeout=10, max_bytes=512*1024)
        text = body.decode("utf-8", "replace")
        if "#EXTINF" not in text and ".ts" not in text:
            # 嵌套playlist
            m = re.search(r'https?://[^\s"]+\.m3u8[^\s"]*', text)
            if not m: return None
            url = m.group(0)
            body, ttfb, _ = fetch(url, timeout=10, max_bytes=512*1024)
            text = body.decode("utf-8", "replace")
        durs = [float(x) for x in re.findall(r"#EXTINF:([\d.]+)", text)]
        lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("#")]
        if not lines or not durs: return None
        segs = lines[-nseg:]
        seg_durs = durs[-nseg:]
        base = url.rsplit("/", 1)[0] + "/"
        total_bytes, total_time, total_dur = 0, 0.0, 0.0
        for s, d in zip(segs, seg_durs):
            su = s if s.startswith("http") else base + s
            b, _, dt = fetch(su, timeout=15)
            total_bytes += len(b); total_time += dt; total_dur += d
        if total_time <= 0 or total_dur <= 0: return None
        kbps = total_bytes * 8 / total_time / 1000
        ratio = total_dur / total_time  # >1 表示跟得上播放
        return {"ttfb": ttfb, "kbps": kbps, "ratio": ratio, "seg_dur": total_dur}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:60]}"}

def probe_raw(url, seconds=8):
    """ts/flv直连: 持续拉seconds秒测吞吐"""
    try:
        body, ttfb, dt = fetch(url, timeout=12, stop_at=seconds+3)
        if dt < 1: return None
        kbps = len(body) * 8 / dt / 1000
        # ts流无法知道真实码率, 按8秒拉到的数据近似(直播流拉到多少=源推多快+带宽下限)
        return {"ttfb": ttfb, "kbps": kbps, "pulled_s": dt, "data_s_equivalent": len(body)/dt/1316}  # 1316B≈0.001s典型ts码率假设不可靠, 仅参考
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:60]}"}

def probe_one(name, url):
    r = probe_m3u8(url) if ".m3u8" in url or "m3u8" in url.lower() else probe_raw(url)
    if r is None: r = {"error": "无法解析"}
    r.update({"name": name, "url": url})
    return r

results = []

# ===== 0) 基线: 家宽下载能力 =====
print("== 基线带宽测试 ==", flush=True)
for label, u in [("腾讯CDN", "https://dldir1.qq.com/qqfile/qq/QQ9.9.16/QQ9.9.16.29271_x64.exe"),
                 ("阿里CDN", "https://npmmirror.com/mirrors/node/v20.11.1/node-v20.11.1-win-x64.zip")]:
    try:
        body, ttfb, dt = fetch(u, timeout=15, max_bytes=30*1024*1024)
        print(f"  {label}: {len(body)/1048576:.1f}MB / {dt:.1f}s = {buf*8/dt/1e6:.1f} Mbps (TTFB {ttfb:.2f}s)", flush=True)
    except Exception as e:
        print(f"  {label}: FAIL {type(e).__name__}", flush=True)

# ===== 1) 自建精选 iptv/live.m3u 逐频道 =====
print("\n== 精选27频道实测 ==", flush=True)
text = open(r"iptv\live.m3u", encoding="utf-8").read()
pairs = re.findall(r'#EXTINF:[^\n]*,(.+)\n(\S+)', text)
with ThreadPoolExecutor(max_workers=4) as ex:
    futs = [ex.submit(probe_one, n.strip(), u) for n, u in pairs]
    for f in futs:
        r = f.result(); results.append(("精选", r))
        if "error" in r: print(f"  [FAIL] {r['name'][:16]}: {r['error']}", flush=True)
        else: print(f"  {r['name'][:16]:18s} {r['kbps']:8.0f} kbps  {r['ratio']:.1f}x实时  TTFB {r['ttfb']:.2f}s", flush=True)

# ===== 2) 日更上游关键频道抽查 =====
print("\n== 日更上游抽查 ==", flush=True)
upstreams = [
    ("咪咕日更", "https://gh-proxy.com/https://raw.githubusercontent.com/Supprise0901/TVBox_live/main/live.txt"),
    ("ChinaIPTV", "https://gh-proxy.com/https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8"),
    ("vbskycn", "https://gh-proxy.com/https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt"),
]
want = ["CCTV1", "CCTV-1", "CCTV5", "CCTV-5", "CCTV13", "CCTV-13", "湖南", "东方", "浙江", "江苏"]
samples = []
for label, u in upstreams:
    try:
        body, _, _ = fetch(u, timeout=20, max_bytes=8*1024*1024)
        t = body.decode("utf-8", "replace")
        for line in t.split("\n"):
            ln = line.strip()
            if not ln or ln.startswith("#"): continue
            m = re.match(r'^(.+?),(.+)$', ln) or (None, None)
            nm = re.sub(r'#.*', '', ln).strip()
            uu = ln
            if m and "http" in m.group(2): nm, uu = m.group(1), m.group(2)
            for w in want:
                if w in nm and "http" in uu:
                    samples.append((f"{label}|{nm[:14]}", uu.split("#")[0].strip()))
                    break
    except Exception as e:
        print(f"  {label} 拉取失败: {e}", flush=True)

seen = set(); uniq = []
for n, u in samples:
    if u not in seen: seen.add(u); uniq.append((n, u))
uniq = uniq[:24]
with ThreadPoolExecutor(max_workers=4) as ex:
    futs = [ex.submit(probe_one, n, u) for n, u in uniq]
    for f in futs:
        r = f.result(); results.append(("上游", r))
        if "error" in r: print(f"  [FAIL] {r['name'][:20]}: {r['error']}", flush=True)
        else: print(f"  {r['name'][:22]:24s} {r['kbps']:8.0f} kbps  {r['ratio'] if 'ratio' in r else 0:.1f}x实时  TTFB {r['ttfb']:.2f}s", flush=True)

# ===== 3) IPV6 可用性 =====
print("\n== IPV6 检测 ==", flush=True)
try:
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    s.settimeout(6)
    s.connect(("2402:4e00:1013:e500:0:940e:29d7:3433", 443))  # qiniu ipv6
    print("  IPV6 可直连", flush=True)
    s.close()
except Exception as e:
    print(f"  IPV6 不可用: {type(e).__name__} {str(e)[:50]}", flush=True)

# ===== 汇总 =====
json.dump(results, open(r"live_probe_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
ok = [r for grp, r in results if "error" not in r and grp == "精选"]
if ok:
    ratios = sorted(x["ratio"] for x in ok)
    print(f"\n== 精选汇总: 存活{len(ok)}/{len(pairs)}  实时倍速中位数 {ratios[len(ratios)//2]:.1f}x  <1.5x(卡顿风险){sum(1 for x in ratios if x<1.5)}条 ==", flush=True)
print("DONE", flush=True)
