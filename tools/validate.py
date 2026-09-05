# -*- coding: utf-8 -*-
"""
仓库质量校验（CI 与本地自检共用, 仅依赖标准库）
检查项:
  1. 仓库内所有 .json 文件均可解析
  2. 含 sites 列表的配置文件中, 站点 key 不得重复
  3. dead_sites.json 的每个 key 必须存在于 anaer_meow.json 且 searchable == 0
用法: python tools/validate.py   (在仓库根目录执行)
全部通过退出码 0, 任一失败退出码 1。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors = []


def check(label, ok, detail=""):
    print(("  [PASS] " if ok else "  [FAIL] ") + label + ((" - " + detail) if detail else ""))
    if not ok:
        errors.append(label + (" - " + detail if detail else ""))


def find_json_files():
    return sorted(p for p in ROOT.rglob("*.json") if ".git" not in p.parts)


def get_sites(doc):
    """返回文件中的站点列表(若无则 None)"""
    if isinstance(doc, dict) and isinstance(doc.get("sites"), list):
        return doc["sites"]
    if isinstance(doc, dict):
        for v in doc.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "key" in v[0]:
                return v
    if isinstance(doc, list) and doc and isinstance(doc[0], dict) and "key" in doc[0]:
        return doc
    return None


def main():
    print("== 1) 全量 JSON 语法检查 ==")
    docs = {}
    for p in find_json_files():
        rel = p.relative_to(ROOT).as_posix()
        try:
            docs[rel] = json.loads(p.read_bytes().decode("utf-8-sig"))
            check("解析 " + rel, True)
        except Exception as e:
            check("解析 " + rel, False, str(e)[:120])

    print("== 2) 站点 key 唯一性 ==")
    for rel, doc in sorted(docs.items()):
        sites = get_sites(doc)
        if sites is None:
            continue
        keys = [s.get("key") for s in sites if isinstance(s, dict)]
        dups = sorted(set(k for k in keys if keys.count(k) > 1))
        check("key 唯一 " + rel + " (%d 站点)" % len(keys), not dups,
              "重复: %s" % dups[:5] if dups else "")

    print("== 3) dead_sites.json 交叉一致性 ==")
    dead_rel = "dead_sites.json"
    meow_rel = "mirror/anaer_meow.json"
    if dead_rel in docs and meow_rel in docs:
        dead_keys = docs[dead_rel].get("keys", [])
        meow = {s.get("key"): s for s in get_sites(docs[meow_rel]) or []}
        missing = [k for k in dead_keys if k not in meow]
        not_zero = [k for k in dead_keys if k in meow and meow[k].get("searchable") != 0]
        check("dead key 存在于 anaer_meow.json (%d 个)" % len(dead_keys), not missing,
              "缺失: %s" % missing[:5] if missing else "")
        check("dead key 均已置 searchable:0", not not_zero,
              "未置零: %s" % not_zero[:5] if not_zero else "")
    else:
        check("交叉一致性", False, "缺少 %s 或 %s" % (dead_rel, meow_rel))

    print()
    if errors:
        print("校验失败: %d 项" % len(errors))
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
