# -*- coding: utf-8 -*-
"""
把 Weekly Probe 的探测输出写回 README 的 health 标记区块。

输入: probe_main.txt / probe_revive.txt（由 .github/workflows/probe.yml 生成于仓库根）
输出: 就地更新 README.md 中 <!-- health:start ... --> 与 <!-- health:end --> 之间的内容
用法: python tools/update_health.py [--date YYYY-MM-DD]
仅依赖标准库；找不到汇总行时以 0 填充，不误判为失败。
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"


def read(name):
    p = ROOT / name
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def number(pattern, text, default=0):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%d"), help="探测日期 (UTC)")
    args = ap.parse_args()

    main_txt = read("probe_main.txt")
    revive_txt = read("probe_revive.txt")
    if not main_txt.strip():
        print("probe_main.txt 为空或不存在，跳过健康区块更新")
        return 0

    total = number(r"总站点\s+(\d+)", main_txt)
    todo = number(r"待探测\(接口/正则且可搜\)\s+(\d+)", main_txt)
    alive = number(r"汇总:\s*可出片\s+(\d+)", main_txt)
    empty = number(r"汇总:.*?空结果\s+(\d+)", main_txt)
    nonjson = number(r"汇总:.*?非JSON响应\s+(\d+)", main_txt)
    dead = number(r"汇总:.*?失活\s+(\d+)", main_txt)
    revived = number(r"复活候选\s+(\d+)\s*个", revive_txt)

    dead_sites = 0
    dead_path = ROOT / "dead_sites.json"
    if dead_path.exists():
        try:
            dead_sites = len(json.loads(dead_path.read_text(encoding="utf-8")).get("keys", []))
        except Exception:
            pass

    block = (
        "| 指标 | 数值 |\n"
        "|---|---|\n"
        "| 最近探测 | %s（UTC，Weekly Probe 自动生成） |\n"
        "| 主力源 | `mirror/anaer_meow.json` |\n"
        "| 总站点 / 待探测 | %d / %d |\n"
        "| 可出片 | %d |\n"
        "| 空结果 | %d |\n"
        "| 非 JSON 响应（未必不可用） | %d |\n"
        "| 失活 | %d |\n"
        "| 复活候选（待人工复核） | %d |\n"
        "| 当前 dead_sites | %d |\n"
    ) % (args.date, total, todo, alive, empty, nonjson, dead, revived, dead_sites)

    text = README.read_text(encoding="utf-8")
    m = re.search(r"(<!-- health:start[^\n]*-->\n)(.*?)(<!-- health:end -->)",
                  text, re.S)
    if not m:
        print("README.md 缺少 health:start / health:end 标记", file=sys.stderr)
        return 1
    new_text = text[:m.start(2)] + "\n" + block + "\n" + text[m.end(2):]
    with open(README, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)
    print("README 源池健康区块已更新 (%s)" % args.date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
