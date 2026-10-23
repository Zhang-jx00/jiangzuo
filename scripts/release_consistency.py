#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核**远端**的发布产物是否自洽（将作 jiangzuo）。

**为什么要有这个**（E39）：本仓库的"发布产物"有两样 —— **tag** 与 **GitHub Release**。
E37 查出过远端 `v0.51.0` 的 tag **指错了 commit**，于是加了第 26 项
（`validate` 的第 26 项核「每个 tag 指向的 commit 真的属于那个版本」）。
但那一条核的是**本地 git 对象** ⇒ 而**远端到底发出去什么**，CI 上**从来没有任何一项在核**：
  · 少发一个 Release ⇒ 没人发现（直到有人去 GitHub 上找）
  · 多发/发错名字的 Release ⇒ 没人发现
  · tag 与 Release 对不上 ⇒ 没人发现
⇒ 这个脚本补的就是这一环。

**只用匿名 API**（不联网要 token、也不写任何凭据）：
  · `GET /repos/{owner}/{repo}/releases?per_page=100`  → 远端 Release 集合
  · `GET /repos/{owner}/{repo}/git/matching-refs/tags/?per_page=100` → 远端 tag 集合
  ⇒ **两次调用** ⇒ 对匿名 API 的 60 次/小时额度很友好（CI 共享 IP ⇒ 必须省）。

**核什么**（三件事）：
  ① 远端 **Release 名字集合 == 远端 tag 名字集合**（一一对应、零缺口）
  ② 远端 **Release 数 == 本地 tag 数**（不多不少；本地 tag 数从 `git tag` 取，零 API 调用）
  ③ 远端 Release 的 `draft` / `prerelease` 状态**如实报出**（不是错，但要看）

**退出码（三态，别混）**：
  0 = 核过了，且一致
  1 = **核过了，且不一致** ⇒ 真问题 ⇒ CI 必红
  2 = **没核成**（限流 / 网络 / 仓库不可达 / API 变了）⇒ **不假绿**：不红，但
      **必须在 workflow 摘要与注解里写明「这轮没核成」**（见 .github/workflows/release-consistency.yml）

⚠️ **为什么不核「每个远端 tag 的 commit 指向」** ⇒ 那要给每个 annotated tag 调一次
  `/git/tags/{sha}` 剥壳 ⇒ 70 个 tag = 70 次调用 ⇒ **会打爆匿名额度** ⇒
  ⇒ 那一层留给 `scripts/release_identity.py --remote`（**带 token**、手动跑、一次到位）。

仅使用 Python 3.8+ 标准库、**不写任何文件**。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
# 仓库身份**只有一处**（E42）：从 `scripts/repo_identity.py` 导入 ⇒ 本文件不再抄一份。
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from repo_identity import OWNER, NAME  # noqa: E402  （必须在本目录里）
API = "https://api.github.com/repos/%s/%s" % (OWNER, NAME)
UA = "jiangzuo-release-consistency"

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_NOT_CHECKED = 2


def _get(url):
    """匿名 GET。返回 (json, headers)。"""
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r), dict(r.headers)


def remote_release_names():
    """远端 Release 的 tag_name 集合（外加 draft/prerelease 计数）。"""
    rels, hdr = _get(API + "/releases?per_page=100")
    if len(rels) >= 100:
        raise RuntimeError("releases 返回 %d 条（>= per_page 上限）⇒ 可能有 Release 没被核到；"
                           "**不静默截断**" % len(rels))
    names = set()
    drafts = prereleases = 0
    for r in rels:
        names.add(r.get("tag_name"))
        if r.get("draft"):
            drafts += 1
        if r.get("prerelease"):
            prereleases += 1
    return names, drafts, prereleases, hdr.get("X-RateLimit-Remaining")


def remote_tag_names():
    """远端 tag 名字集合（`refs/tags/xxx` ⇒ 取最后一段）。"""
    refs, hdr = _get(API + "/git/matching-refs/tags/?per_page=100")
    if len(refs) >= 100:
        raise RuntimeError("matching-refs 返回 %d 条（>= per_page 上限）⇒ 可能有 tag 没被核到；"
                           "**不静默截断**" % len(refs))
    return set(r["ref"].split("/")[-1] for r in refs), hdr.get("X-RateLimit-Remaining")


def local_tag_names():
    """本地 tag 名字集合（零 API 调用；CI 上有 git）。"""
    p = subprocess.run(["git", "-C", REPO, "tag", "--list", "v*"],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return set(t for t in p.stdout.decode("utf-8", "replace").split() if t)


def check():
    """返回 (exit_code, 结论行列表)。"""
    out = []
    try:
        rel_names, drafts, prereleases, rl1 = remote_release_names()
        tag_names, rl2 = remote_tag_names()
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            out.append("**没核成**：GitHub API 限流或拒绝匿名访问（HTTP %s）"
                       "⇒ 这轮**不判通过、也不判失败**（见退出码 2 的说明）" % e.code)
            return EXIT_NOT_CHECKED, out
        out.append("**没核成**：GitHub API 返回 HTTP %s" % e.code)
        return EXIT_NOT_CHECKED, out
    except Exception as e:      # noqa: BLE001 —— 网络异常一律"没核成"，不当通过
        out.append("**没核成**：访问 GitHub API 失败（%s）" % e)
        return EXIT_NOT_CHECKED, out

    out.append("远端 Release %d 个 ／ 远端 tag %d 个（匿名额度剩余 %s → %s）"
               % (len(rel_names), len(tag_names), rl1, rl2))
    if drafts or prereleases:
        out.append("（其中 draft %d 个、prerelease %d 个 —— 不是错，但要看得见）"
                   % (drafts, prereleases))

    local = local_tag_names()
    if local:
        out.append("本地 tag %d 个" % len(local))
    else:
        out.append("本地 **没有 tag**（浅克隆 / 未 fetch tags）⇒ 「远端 Release 数 vs 本地 tag 数」"
                   "这一项**这轮没核**（不是\"通过\"）")

    problems = []
    only_rel = sorted(rel_names - tag_names)
    only_tag = sorted(tag_names - rel_names)
    if only_rel:
        problems.append("**有 Release 没有对应 tag**：%s" % "、".join(only_rel))
    if only_tag:
        problems.append("**有 tag 没有对应 Release**：%s" % "、".join(only_tag))
    if local and len(rel_names) != len(local):
        problems.append("**远端 Release 数 %d ≠ 本地 tag 数 %d**（多发或少发了？）"
                        % (len(rel_names), len(local)))

    if problems:
        for p in problems:
            out.append(p)
        return EXIT_MISMATCH, out
    out.append("✓ 远端 Release 与远端 tag **一一对应、零缺口**"
               + ("，且数量与本地一致" if local else "（本地无 tag ⇒ 数量那项未核）"))
    return EXIT_OK, out


def main():
    ap = argparse.ArgumentParser(description="将作：核远端发布产物是否自洽（tag ↔ Release）")
    ap.add_argument("--check", action="store_true", help="核验（默认行为）")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:      # pragma: no cover
        pass
    code, out = check()
    for line in out:
        print(line)
    if code == EXIT_NOT_CHECKED:
        print("⇒ 退出码 2：**这轮没核成**（不是\"通过\"）——CI 应当把这句话原样写进摘要，"
              "别让一个没跑的核验看起来像跑过了")
    elif code == EXIT_MISMATCH:
        print("⇒ 退出码 1：**核过了，且不一致** —— 远端发布产物与 tag 对不上")
    else:
        print("⇒ 退出码 0：核过了，且一致")
    return code


if __name__ == "__main__":
    sys.exit(main())
