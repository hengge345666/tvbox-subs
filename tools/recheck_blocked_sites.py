# -*- coding: utf-8 -*-
"""
台账复核工具：检查 mirror/anaer_meow.json 中被 excluded_sites.json 台账标记为
"应屏蔽"的站点，是否被上游 auto-sync 回滚（searchable/quickSearch 被重置为 1）。

用法:
    python tools/recheck_blocked_sites.py            # 仅报告
    python tools/recheck_blocked_sites.py --fix      # 报告并自动修复被回滚的站点

退出码: 0 = 全部保持屏蔽; 1 = 存在被回滚站点(需 --fix 或人工处理)

输出:
  [OK]        屏蔽状态与台账一致
  [NEEDS_FIX] 被回滚, 需要修复
  [MISSING]   台账记录的 key 已不在当前文件(上游已移除, 属正常收敛)

依赖: 仅 Python 标准库; 以 UTF-8 读写, 保持与源文件一致的行尾。
"""
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = "mirror/anaer_meow.json"
LEDGER = "tools/excluded_sites.json"


def load_json(path):
    with io.open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def collect_ledger_keys(ledger):
    """从台账提取所有需保持屏蔽的 key -> {name, reason}。

    覆盖两类记录:
      1. 顶层散 key 记录(如 0ec30b24... 的 md5 键)
      2. batch_* 批次记录中的 sites 列表
    跳过 restored 数组中已恢复的 key。
    """
    blocked = {}
    restored = {r["key"] for r in ledger.get("restored", []) or [] if r.get("key")}

    # 顶层散 id 记录: 值为 dict 且含 name/reason
    for k, v in ledger.items():
        if not isinstance(v, dict):
            continue
        if v.get("name") and (v.get("reason") or v.get("by")):
            if k not in restored:
                blocked[k] = {"name": v.get("name", ""), "reason": v.get("reason", "")}

    # batch_* 批次
    for k, v in ledger.items():
        if not (isinstance(v, dict) and k.startswith("batch_")):
            continue
        for s in v.get("sites", []) or []:
            key = s.get("key")
            if not key or key in restored:
                continue
            blocked[key] = {"name": s.get("name", ""), "reason": s.get("reason", "")}
    return blocked


def main():
    fix = "--fix" in sys.argv
    ledger = load_json(LEDGER)
    blocked = collect_ledger_keys(ledger)

    data = load_json(SRC)
    sites = {s.get("key"): s for s in data.get("sites", [])}

    ok_list, need_fix, missing = [], [], []
    for key, meta in blocked.items():
        s = sites.get(key)
        if s is None:
            missing.append((meta["name"], meta["reason"]))
            continue
        if s.get("searchable") == 0 and s.get("quickSearch") == 0:
            ok_list.append((meta["name"], meta["reason"]))
        else:
            need_fix.append((key, meta["name"], meta["reason"],
                             s.get("searchable"), s.get("quickSearch")))

    print("== 台账应屏蔽 %d 个 | anaer_meow 当前 %d 站 ==" % (len(blocked), len(sites)))
    print()
    print("[OK] 保持屏蔽: %d 个" % len(ok_list))
    for name, reason in ok_list:
        print("   - %-22s %s" % (name, (reason or "")[:50]))
    print()
    print("[MISSING] 已不在文件(上游移除, 正常): %d 个" % len(missing))
    for name, reason in missing:
        print("   - %-22s %s" % (name, (reason or "")[:50]))
    print()
    print("[NEEDS_FIX] 被 auto-sync 回滚: %d 个" % len(need_fix))
    for key, name, reason, s0, q0 in need_fix:
        print("   - %-22s key=%s searchable=%s quickSearch=%s | %s" % (
            name, key, s0, q0, (reason or "")[:50]))

    if need_fix:
        if not fix:
            print()
            print(">> 发现 %d 个被回滚站点, 运行 'python tools/recheck_blocked_sites.py --fix' 自动修复"
                  % len(need_fix))
        else:
            print()
            print("== 执行 --fix ==")
            for key, name, reason, _s, _q in need_fix:
                if key in sites:
                    sites[key]["searchable"] = 0
                    sites[key]["quickSearch"] = 0
                    print("   fixed: %s (%s)" % (name, key))
            with io.open(SRC, "w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("已写回 %s" % SRC)
    return 1 if need_fix else 0


if __name__ == "__main__":
    sys.exit(main())