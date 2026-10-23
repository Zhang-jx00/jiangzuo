#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成/发布 GitHub Release 的发行说明（将作 jiangzuo）。

**发行说明的单一真源是 `CHANGELOG.md`** —— 每个版本的条目就是那一发的正文。
为什么不给 60 多个版本各手抄一份：手抄的副本会**随实现演进而漂移**
（这项目已经吃过"手数的偏差会自我延续"的亏）⇒ 一次生成、永远同步。

用法：
    python scripts/release_notes.py --version 0.66.0          # 打印那一发的发行说明
    python scripts/release_notes.py --check                  # 核对每个 tag 都有条目
    python scripts/release_notes.py --check --write          # 把每一发的说明写进
                                                             # docs/jiangzuo/releases/
    python scripts/release_notes.py --publish --token <TOKEN>  # 建 GitHub Release

仅使用 Python 3.8+ 标准库、**不联网**（--publish 例外，它要调 GitHub API）。
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

# ⚠️ Windows 控制台默认 GBK ⇒ 打印「⇒」这类字符会 UnicodeEncodeError。
#    E37 实测：崩的时机恰好是**要拒发 Release 的时候**（那句提示里就有 ⇒）
#    ⇒ 最需要它说话时哑了 ⇒ 而且崩在发布流程的**最关键一步**上。
#    ⇒ 统一把两个流切到 UTF-8（Linux/macOS 上是无害的 no-op）。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CHANGELOG = os.path.join(REPO, "CHANGELOG.md")
RELEASES_DIR = os.path.join(REPO, "docs", "jiangzuo", "releases")
# 仓库身份**只有一处**（E42）：owner/name 与各种 URL 从 `scripts/repo_identity.py` 导入
# ⇒ 本文件**不再**抄一份（发行说明里的克隆地址也由它派生 ⇒ 仓库改名时不会指向旧地址）。
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from repo_identity import OWNER, NAME, CLONE_URL  # noqa: E402  （必须在本目录里）

# E37：发布产物的**身份**核验在另一个脚本里（`scripts/release_identity.py`）。
# 同一份实现，不复制第二份——复制出来的两份迟早会不一致，而不一致的那份没人核。
if HERE not in sys.path:
    sys.path.insert(0, HERE)
try:
    import release_identity
except ImportError:            # pragma: no cover —— 脚本单独拷走时的兜底
    release_identity = None

BOUNDARY_NOTE = """## 已知边界（不藏）

- 完整清单见 `references/audit-rule-authoring.md` 的「能力边界表」——
  **每条带"为什么做不到 + 代价 + 实测证据"，并用最小夹具钉住** ⇒ 引擎演进时测试会红、提醒改表。
- 三条最常被问到的：
  - **"没报"≠"安全"**：缺失型判据（暴力破解 / 验证码 / 速率限制）与跨请求、存储型数据流
    需要中间件 / 请求视角 ⇒ 静态扫描原理上拿不到，已交人工。
  - **规则默认在「掩码桶」上跑** ⇒ 看不见字符串内部（PHP < 5.5 的 `preg_replace('/x/e')` 当前检不出）。
  - **JS 里 `//` 的歧义**（注释 / 正则字面量 / 除法）⇒ 我们按注释处理，正则字面量同行之后的代码会被漏掉。
"""

INSTALL = """## 安装与使用

```bash
git clone {clone_url}
# 复制到你的技能目录（Claude / ZCode / Codex / Cursor / Gemini CLI / OpenCode 通用）
cp -r {name} ~/.claude/skills/          # 或 ~/.zcode/skills/、~/.agents/skills/
```

脚本**零依赖**（只用 Python 3.8+ 标准库）、**不联网**、**不改被扫项目**；
全项目审计链十步：索引 → 地图 → 粗筛 → 深挖 → 污点流 → 独立验证 → 分级 → 报告（MD/JSON/SARIF 2.1.0）→ 人工确认 → 续扫。
"""


def read_changelog():
    with io.open(CHANGELOG, encoding="utf-8") as f:
        return f.read()


def entries(text):
    """{版本号: (日期, 正文)} —— 正文的**首行去掉标题**，其余原样。"""
    out = {}
    parts = re.split(r"^##\s*\[(\d+\.\d+\.\d+)\]\s*-\s*(\d{4}-\d{2}-\d{2})\s*$",
                     text, flags=re.M)
    # parts = [pre, v1, d1, body1, v2, d2, body2, ...]
    for i in range(1, len(parts) - 2, 3):
        ver, date, body = parts[i], parts[i + 1], parts[i + 2]
        out[ver] = (date, body.rstrip("\n"))
    return out


def tags():
    p = subprocess.run(["git", "tag", "--list", "v*"], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return sorted([t for t in p.stdout.decode("utf-8").split() if t])


def tag_commit(tag):
    """(日期, 提交说明) —— CHANGELOG 缺条目时的**兜底事实来源**。"""
    p = subprocess.run(["git", "log", "-1", "--format=%cI%x00%B", tag], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    out = p.stdout.decode("utf-8", "replace")
    if "\x00" not in out:
        return (None, None)
    date, msg = out.split("\x00", 1)
    return (date.strip()[:10], msg.strip())


def tag_sha(tag):
    """tag 指向的 commit sha（解引用后）—— 发布时要拿它当 `target_commitish`。"""
    p = subprocess.run(["git", "rev-list", "-1", tag], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return p.stdout.decode("utf-8", "replace").strip()


def remote_tag_map(token=None):
    """{tag: commit} —— 远端 tag 指向的 commit；**核不到返回 None**。

    核不到不是"通过"⇒ 调用方必须拒绝发布（见 `do_publish`）。
    ⚠️ token 要传下去：`release_identity.remote_tags` 在 **git 传输通道不通**时
    会回退到 **API 通道**（E37 实测：那天 `github.com:443` 在 TLS 层被选择性阻断，
    而 `api.github.com` 正常 ⇒ 没回退的话 Release 发不出去）。
    """
    if release_identity is None:
        return None
    try:
        m = release_identity.remote_tags(release_identity.REPO, token)
    except Exception:           # noqa: BLE001 —— 网络/远端异常都算"核不到"
        return None
    return m or None


def strip_markers(body):
    """去掉「当前状态」标记行（E34）。

    为什么：CHANGELOG 的最新条目里有一块 `<!-- current-state:begin/end -->`
    标记区，那是给校验器对账用的**机器锚点** ⇒ 不该出现在发布出去的正文里
    （HTML 注释虽不可见，但它是内部约定，不该外泄给读者）。
    标记区**内容**保留——它本身就是"这一发的当前状态"，对读者有用。
    """
    out = []
    for line in body.split("\n"):
        s = line.strip()
        if s.startswith("<!-- current-state:") and s.endswith("-->"):
            continue
        out.append(line)
    return "\n".join(out)


def notes_for(ver, date, body, fallback=False):
    body = strip_markers(body)
    lines = [l.rstrip() for l in body.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    # 标题取**第一段**（到第一个空行为止）—— CHANGELOG 的首行常常是半句话
    para = []
    for l in lines:
        if not l.strip():
            break
        para.append(l.strip())
    title = " ".join(para)
    rest = "\n".join(lines[len(para):]).strip("\n")
    if len(title) > 110:
        title = title[:110].rstrip() + "…"
    parts = ["# 将作 v%s 发行说明" % ver, "",
             "> 发行日期：%s ｜ 仓库：https://github.com/%s/%s ｜ tag：`v%s`" % (date, OWNER, NAME, ver),
             ">",
             "> 发行说明的**单一真源是 `CHANGELOG.md`**（由 `scripts/release_notes.py` 生成）⇒ 不会与实现漂移。"]
    if fallback:
        parts.append(">")
        parts.append("> ⚠️ **该版本的 `CHANGELOG.md` 条目缺失**（历史遗留的台账洞，v0.15.0–v0.19.0 五版）"
                     "⇒ 本说明**取自该 tag 的提交说明**（同样是事实来源，只是没进 CHANGELOG）。")
    parts += ["", "## 这一发里有什么", "", "### %s" % title, ""]
    if rest:
        parts.append(rest)
        parts.append("")
    parts.append(BOUNDARY_NOTE)
    parts.append(INSTALL.format(clone_url=CLONE_URL, name=NAME))
    parts.append("## 文档索引")
    parts.append("")
    parts.append("- 逐版本记录：`CHANGELOG.md`（**唯一真源**）")
    parts.append("- 逐轮决策账本：`docs/jiangzuo/evolution.md`")
    parts.append("- 交接文档（接手时先看 §0 的 10 行）：`docs/jiangzuo/handover.md`")
    parts.append("- 结论区逐条判定表：`evals/finding-verdicts.md`")
    parts.append("- 文档结构见 `docs/jiangzuo/reports/2026-10-15-delivery-v0.36.1.md`")
    return "\n".join(parts).rstrip() + "\n"


def resolve(ver, ent):
    """返回 (日期, 正文, 是否用了兜底)。"""
    if ver in ent:
        date, body = ent[ver]
        return (date, body, False)
    date, msg = tag_commit("v" + ver)
    return (date or "（未知日期）", msg or ("（该 tag 的提交说明为空）"), True)


def do_check(write=False):
    text = read_changelog()
    ent = entries(text)
    tg = tags()
    fallback = [t for t in tg if t[1:] not in ent]
    print("CHANGELOG 条目 %d 个 ｜ tag %d 个 ｜ 走兜底（tag 提交说明）%d 个"
          % (len(ent), len(tg), len(fallback)))
    if fallback:
        print("CHANGELOG 缺条目的 tag：%s" % "、".join(fallback))
    if write:
        if not os.path.isdir(RELEASES_DIR):
            os.makedirs(RELEASES_DIR)
        n = 0
        for t in tg:
            ver = t[1:]
            date, body, fb = resolve(ver, ent)
            p = os.path.join(RELEASES_DIR, "%s.md" % t)
            with io.open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(notes_for(ver, date, body, fb))
            n += 1
        print("已写出 %d 份发行说明 → docs/jiangzuo/releases/" % n)
    return 0


def publish_blockers(remote_map, want_map):
    """发布前的**拦路项**：逐条说清"这个 tag 为什么不能发"。

    remote_map: {tag: 远端 tag 指向的 commit}
    want_map:   {tag: 本地 tag 指向的 commit}

    这条纯函数是为了**可测**（E37 的判据要能红），逻辑与 `do_publish` 用的是同一份。
    """
    blocked = []
    for t in sorted(want_map):
        want = want_map.get(t)
        got = remote_map.get(t)
        if got is None:
            blocked.append(u"%s（远端**没有**这个 tag ⇒ 先 `git push origin %s`；"
                           u"GitHub 会自动在 main HEAD 上造同名 tag，不能让它发生）" % (t, t))
        elif want and got != want:
            blocked.append(u"%s（远端指向 %s，本地是 %s ⇒ 先把远端 tag 修对再发）"
                           % (t, got[:7], want[:7]))
    return blocked


def do_publish(token, only=None):
    import urllib.request
    ent = entries(read_changelog())
    tg = tags()
    if only:
        tg = ["v" + only]

    # ── E37：发布前**必须**核远端 tag 的身份 ──────────────────────────────
    # 为什么这一步不能省（真实教训）：`POST /releases` 若**不带** `target_commitish`，
    # GitHub 用默认分支 main；而当远端还没有这个 tag 时，GitHub 会在 main 的 HEAD 上
    # **自动造出**一个同名 tag —— 名字对，内容是当时 main 的内容。
    # E37 查出远端 `v0.51.0` 就是这样来的：它指向 `d5b88e1a`（v0.66.0 的补记笔），
    # 而不是 v0.51.0 的代码 ⇒ 谁 checkout v0.51.0 拿到的都是别的版本。
    # 而「68 tag / 68 Release 一一对应、零缺口」当时是**真的**——它只数了名字与数量。
    # ⇒ 这里改成：**远端 tag 不存在或指向不对 ⇒ 拒绝发布**，并说清要做什么。
    rtags = remote_tag_map(token)
    if rtags is None:
        print("核不到远端 tag（ls-remote 失败或 remote 不对）⇒ 拒绝发布。")
        print("  宁可不发，也不在 main HEAD 上自动造出一个同名 tag。")
        return 2
    want_map = dict((t, tag_sha(t)) for t in tg)
    blocked = publish_blockers(rtags, want_map)
    if blocked:
        print("**拒绝发布**：%d 个 tag 的远端身份不对（宁可不发，也不在 main HEAD 上造 tag）"
              % len(blocked))
        for b in blocked:
            print("  ! " + b)
        return 2

    api = "https://api.github.com/repos/%s/%s/releases" % (OWNER, NAME)
    hdr = {"Authorization": "token " + token, "Accept": "application/vnd.github+json",
           "User-Agent": "jiangzuo-release"}
    created, skipped, failed = [], [], []
    for t in tg:
        ver = t[1:]
        date, body, fb = resolve(ver, ent)
        req = urllib.request.Request(api, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                existing = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                failed.append("%s（列 %s 出错 %s）" % (t, e.code, e.reason))
                continue
            existing = []
        if any(x.get("tag_name") == t for x in existing):
            skipped.append("%s（已存在）" % t)
            continue
        payload = {
            "tag_name": t,
            "name": "将作 v%s" % ver,
            "body": notes_for(ver, date, body, fb),
            "draft": False,
            "prerelease": False,
            # 双保险：显式指定该 tag 应指向的 commit。
            # tag 已存在时 GitHub 会忽略它；万一它不存在，也不会落到 main HEAD 上。
            "target_commitish": tag_sha(t),
        }
        req = urllib.request.Request(api, data=json.dumps(payload).encode("utf-8"),
                                     headers=dict(hdr, **{"Content-Type": "application/json"}),
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                got = json.load(r)
            created.append("%s → %s" % (t, got.get("html_url", "?")))
        except urllib.error.HTTPError as e:
            failed.append("%s（%s %s）" % (t, e.code, e.reason))
        except Exception as e:
            failed.append("%s（%s）" % (t, e))
    print("已发布 %d ｜ 跳过 %d ｜ 失败 %d" % (len(created), len(skipped), len(failed)))
    for x in created:
        print("  + " + x)
    for x in skipped:
        print("  = " + x)
    for x in failed:
        print("  ! " + x)
    if created:
        # 发完**回头自证**：远端 tag 指向必须仍与本地一致（不许默默漂移）。
        problems, summary = release_identity.check_remote(token, verbose=False)
        if problems:
            print("**发完自证不过**：")
            for p in problems:
                print("  ! " + p)
            return 1
        print("发完自证：远端 %d 个 tag 与本地逐条同 commit，Release %d 个 ✓"
              % (summary.get("remote_tags", 0), summary.get("releases", 0)))
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description="将作：发行说明生成 / GitHub Release 发布")
    ap.add_argument("--version", help="只处理某个版本（不带 v）")
    ap.add_argument("--check", action="store_true", help="核对每个 tag 都有 CHANGELOG 条目")
    ap.add_argument("--write", action="store_true", help="把发行说明写进 docs/jiangzuo/releases/")
    ap.add_argument("--publish", action="store_true", help="创建 GitHub Release")
    ap.add_argument("--token", help="GitHub token（--publish 需要）")
    args = ap.parse_args()
    if args.publish:
        if not args.token:
            print("--publish 需要 --token", file=sys.stderr)
            return 2
        return do_publish(args.token, args.version)
    if args.version:
        ent = entries(read_changelog())
        date, body, fb = resolve(args.version, ent)
        if date is None:
            print("既没有 CHANGELOG 条目、也取不到 v%s 的提交说明" % args.version,
                  file=sys.stderr)
            return 2
        sys.stdout.write(notes_for(args.version, date, body, fb))
        return 0
    return do_check(args.write)


if __name__ == "__main__":
    sys.exit(main())
