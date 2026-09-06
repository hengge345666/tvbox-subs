# -*- coding: utf-8 -*-
"""
订阅与更新链路可达性检查（CI 用, 仅依赖标准库）
检查项:
  1. subs.json 每条订阅 URL 必须为 https:// 且可访问（明文 http 直接判失败）
  2. version.json 的 apk / apkArm64 / apkUniversal 链接可访问
  3. version.json 的 sha256* 字段（若有）必须为 64 位十六进制
判定: HEAD 优先, 服务器不支持 HEAD(405/501) 或瞬时失败时回退 Range GET; 2xx/3xx 视为可达。
用法: python tools/check_urls.py   (在仓库根目录执行; 建议在 CI 环境运行,
      本地办公网络直连 GitHub 可能误报)
全部通过退出码 0, 任一失败退出码 1。
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; tvbox-subs-ci/1.0)"}
errors = []


def check(label, ok, detail=""):
    print(("  [PASS] " if ok else "  [FAIL] ") + label + ((" - " + detail) if detail else ""))
    if not ok:
        errors.append(label + ((" - " + detail) if detail else ""))


def reachable(url, timeout=20):
    """返回 (ok, status)。HEAD 优先, 405/501 或网络异常时回退 Range GET。"""
    attempts = (("HEAD", {}), ("GET", {"Range": "bytes=0-0"}))
    last = "unreachable"
    for method, extra in attempts:
        req = urllib.request.Request(url, headers={**UA, **extra}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return True, resp.status
        except urllib.error.HTTPError as e:
            if e.code in (405, 501) and method == "HEAD":
                last = "HTTP %d" % e.code
                continue
            return False, "HTTP %d" % e.code
        except Exception as e:
            last = type(e).__name__
            continue
    return False, last


def main():
    print("== 1) subs.json 订阅可达性与 https 检查 ==")
    subs = json.loads((ROOT / "subs.json").read_bytes().decode("utf-8-sig"))
    for i, item in enumerate(subs.get("urls", []), 1):
        name = str(item.get("name", "?"))
        u = str(item.get("url", "")).strip()
        if not u:
            check("订阅%d %s 有 URL" % (i, name), False, "字段缺失")
            continue
        if not u.startswith("https://"):
            check("订阅%d %s 为 https" % (i, name), False, u[:80])
            continue
        ok, st = reachable(u)
        check("订阅%d %s 可达" % (i, name), ok,
              ("HTTP %s" % st) if ok else ("%s @ %s" % (st, u[:70])))

    print("== 2) version.json 更新链路 ==")
    ver_path = ROOT / "version.json"
    if not ver_path.exists():
        check("version.json 存在", False, "文件缺失")
    else:
        ver = json.loads(ver_path.read_bytes().decode("utf-8-sig"))
        for field in ("apk", "apkArm64", "apkUniversal"):
            u = str(ver.get(field, "")).strip()
            if not u:
                check("%s 存在" % field, False, "字段缺失")
                continue
            ok, st = reachable(u)
            check("%s 可达" % field, ok,
                  ("HTTP %s" % st) if ok else ("%s @ %s" % (st, u[:70])))
        for field, val in ver.items():
            if field.startswith("sha256"):
                check("version.json %s 为 64 位十六进制" % field,
                      bool(re.fullmatch(r"[0-9a-fA-F]{64}", str(val))),
                      str(val)[:24] + ("…" if len(str(val)) > 24 else ""))

    print()
    if errors:
        print("可达性检查失败: %d 项" % len(errors))
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
