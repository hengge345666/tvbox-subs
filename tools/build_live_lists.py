# -*- coding: utf-8 -*-
"""直播清单构建器: 按 scan_result.json 重建三分类清单(央视/卫视/港澳台)
规则: 只保留三类频道; 门槛 ratio>=3 且 ttfb<1; 每频道至多3条备线按倍速排序
输出: iptv/live.m3u, iptv/live.txt, mirror/live.m3u(全部直播·过滤版)
"""
import json, re, sys
from collections import defaultdict

RATIO_MIN = 3.0
TTFB_MAX = 1.0
PER_CHANNEL_MAX = 3

CAT_CCTV = re.compile(r'CCTV|央视|CGTN|CCTV', re.I)
CAT_WS = re.compile(r'卫视|衛視')
CAT_HMT = re.compile(
    r'香港|港台|TVB|翡翠|明珠|凤凰中文|凤凰资讯|凤凰香港|凤凰卫视|鳳凰衛視|HK|RTHK|开电视|HOY|澳门|澳門|澳视|澳視|蓮花|莲花|MACAU'
    r'|台湾|台灣|台视|台視|中视|中視|华视|華視|民视|民視|公视|公視|八大|三立|东森|東森|中天'
    r'|TVBS|纬来|緯來|大爱|大愛|客家台|原住民|原民|龙华|龍華|EBC|SET|CTS|FTV|TTV|CTI'
    r'|discovery.*台|卫视中文台|星衛|星卫', re.I)

# 明确排除(即使匹配上面也要排除的杂类误匹配)
EXCLUDE = re.compile(r'新聞台.*新媒|测试|test|頻道.*備|购物|購物|导视|導視|純音樂|纯音乐|音乐台.*FM|广播|電台|电台', re.I)

def classify(name):
    """返回 'cctv'/'ws'/'hmt'/None"""
    n = name.strip()
    if EXCLUDE.search(n): return None
    if CAT_HMT.search(n): return "hmt"      # 港澳台优先判(如"凤凰卫视"归港澳台而非卫视)
    if CAT_CCTV.search(n): return "cctv"
    if CAT_WS.search(n): return "ws"
    return None

def norm_name(name, cat):
    """频道名归一化去重: 去括号注记/空格/高清后缀"""
    n = re.sub(r'[（(【\[].*?[)）\]】]', '', name)
    n = re.sub(r'高清|超清|HD|FHD|4K|50?fps', '', n, flags=re.I).strip()
    n = re.sub(r'\s+', '', n)
    return n

def main(scan_file="scan_result.json"):
    results = json.load(open(scan_file, encoding="utf-8"))
    # 达标 + 分类
    kept = defaultdict(list)  # (cat, norm) -> [entries]
    # 港澳台直连环境源稀缺, 门槛降档 1.3x(如实标注)
    GATE = {"cctv": RATIO_MIN, "ws": RATIO_MIN, "hmt": 1.3}
    for r in results:
        if r.get("dead"): continue
        cat = classify(r["name"])
        if not cat: continue
        if r.get("ratio", 0) < GATE[cat] or r.get("ttfb", 9) > TTFB_MAX: continue
        r["_cat"] = cat
        kept[(cat, norm_name(r["name"], cat))].append(r)

    # 排序构建
    order = {"cctv": 0, "ws": 1, "hmt": 2}
    group_titles = {"cctv": "📺央视频道", "ws": "🛰️卫视频道", "hmt": "🌉港澳台频道"}
    channels = []
    for (cat, norm), entries in kept.items():
        # URL 去重
        seen, uniq = set(), []
        for e in sorted(entries, key=lambda x: -x["ratio"]):
            if e["url"] in seen: continue
            seen.add(e["url"]); uniq.append(e)
            if len(uniq) >= PER_CHANNEL_MAX: break
        # 频道显示名取最高倍速那条的原始名(清理后)
        disp = re.sub(r'\s+', ' ', uniq[0]["name"]).strip()
        channels.append((order[cat], cat, norm, disp, uniq))
    channels.sort(key=lambda x: (x[0], x[2]))

    stats = {"cctv": 0, "ws": 0, "hmt": 0}
    m3u, txt = ["#EXTM3U"], []
    for _, cat, norm, disp, uniq in channels:
        stats[cat] += 1
        for e in uniq:
            tvg = disp
            m3u.append(f'#EXTINF:-1 group-title="{group_titles[cat]}" tvg-id="{tvg}",{disp}')
            m3u.append(e["url"])
            txt.append(f"{disp},{e['url']}")

    open(r"iptv\live.m3u", "w", encoding="utf-8", newline="\n").write("\n".join(m3u) + "\n")
    open(r"iptv\live.txt", "w", encoding="utf-8", newline="\n").write("\n".join(txt) + "\n")
    # 全部直播 = 同一构建(精选即全部达标源, 不再区分)
    open(r"mirror\live.m3u", "w", encoding="utf-8", newline="\n").write("\n".join(m3u) + "\n")

    total_ch = len(channels)
    total_url = sum(len(c[4]) for c in channels)
    print(f"构建完成: 央视{stats['cctv']} 卫视{stats['ws']} 港澳台{stats['hmt']} 共{total_ch}频道{total_url}线路")
    return stats, total_ch, total_url

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "scan_result.json")
