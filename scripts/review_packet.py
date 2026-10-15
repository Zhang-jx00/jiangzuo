#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审查工单（将作）—— 把"交给审查者/子代理的东西"钉成一个文件

为什么要有它：多轮对话里散着的描述会在上下文压缩后丢掉，而"我说我做了"和
"我做了"是两件事。这个脚本把四样东西固定进一个文件：
**实际改了什么（diff）、任务原话、验收标准、验证命令**，外加一张四态回执。

它**只读不执行**：列出的验证命令是给人与上游看的，脚本一条都不会跑
（有专门的测试锁这一点）。diff 逐行过 `auditlib.redact()`，
避免把刚扫出来的密钥原样抄进交付物。

用法:
    python scripts/review_packet.py --root . --out ../review.md
        [--base HEAD] [--brief "任务原话"] [--claim "一句话主张"]
        [--acceptance-file accept.md] [--verify-cmd "pytest -q"]...
        [--max-diff-kb 200]

仅使用 Python 标准库（3.8+）。
"""
from __future__ import print_function

import argparse
import io
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import auditlib   # noqa: E402

STATES = [
    (u"DONE", u"做完了，且下面每条验收都有跑过的证据",
     u"→ 进审查；证据栏必须已填真命令输出，不是\"应该没问题\""),
    (u"CONCERNS", u"做完了但我知道哪里不对（设计妥协、覆盖不全、可疑邻近改动）",
     u"→ 交回上游决策，别自己捂着；把顾虑写成可回答的问题"),
    (u"NEEDS_CONTEXT", u"缺信息，缺的那条不补上就只能靠猜",
     u"→ 停手，列出缺什么；不要用合理猜测冒充需求"),
    (u"BLOCKED", u"有活干不了（环境、权限、依赖、上游决定未下）",
     u"→ 停手，报阻塞点 + 建议的绕行方案；不要静默降级交付"),
]


def git(root, *args):
    """跑 git；返回 (退出码, 文本)。git 不可用/无仓库时给可读错误而不是崩栈。"""
    try:
        p = subprocess.run(["git", "-C", root] + list(args),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, u"git 不可用：%s" % exc
    return p.returncode, p.stdout.decode("utf-8", "replace")


def redact_line(text):
    out = auditlib.redact(text)
    return out, (0 if out == text else 1)


def main():
    ap = argparse.ArgumentParser(
        description=u"审查工单（将作）：把 diff + 任务原话 + 验收标准 + 验证命令 + 四态回执钉成一个文件。只读，不执行任何验证命令。")
    ap.add_argument("--root", default=".", help=u"项目目录（需是 git 仓库）")
    ap.add_argument("--base", default="HEAD",
                    help=u"对比基准；默认 HEAD（即「工作树相对最近一次提交」）")
    ap.add_argument("--brief", default=u"", help=u"任务原话，逐字记录")
    ap.add_argument("--claim", default=u"", help=u"一句话可证伪主张（交付报告 §0 同一件事）")
    ap.add_argument("--acceptance-file", default=None, help=u"验收标准文件（逐条抄进工单）")
    ap.add_argument("--verify-cmd", dest="verify_cmds", action="append", default=[],
                    help=u"验证命令，可多次；**只列出，不执行**")
    ap.add_argument("--max-diff-kb", type=int, default=200,
                    help=u"diff 正文上限（KB）；超了截断并留痕")
    ap.add_argument("--out", default=None, help=u"输出文件；不给则打到 stdout")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    code, _ = git(root, "rev-parse", "--git-dir")
    if code != 0:
        print(u"错误：%s 不是 git 仓库（工单必须有 diff 基准）" % root, file=sys.stderr)
        return 2
    rc_base, _ = git(root, "rev-parse", args.base)
    if rc_base != 0:
        print(u"错误：基准 %s 解析不了（新仓库还没有提交？先提交基线再来）" % args.base,
              file=sys.stderr)
        return 2

    _, stat = git(root, "diff", args.base, "--stat")
    _, diff = git(root, "diff", args.base, "--unified=3")
    _, untracked = git(root, "ls-files", "--others", "--exclude-standard")

    diff_lines = diff.splitlines()
    budget = max(1, args.max_diff_kb) * 1024
    kept, used, truncated = [], 0, False
    redactions = 0
    for ln in diff_lines:
        safe, n = redact_line(ln)
        redactions += n
        if used + len(safe) + 1 > budget:
            truncated = True
            break
        kept.append(safe)
        used += len(safe) + 1

    acceptance = u""
    if args.acceptance_file:
        path = os.path.abspath(args.acceptance_file)
        if not os.path.isfile(path):
            print(u"错误：验收标准文件不存在：%s" % path, file=sys.stderr)
            return 2
        acceptance = io.open(path, encoding="utf-8").read().strip()

    out = [u"# 审查工单（将作）", u"",
           u"> 仓库：`%s` ｜ 基准：`%s` ｜ 生成方式：`review_packet.py`（只读，不执行任何验证命令）"
           % (root, args.base), u""]
    if args.claim:
        out += [u"## 主张（一句话、可证伪）", u"", args.claim, u""]
    out += [u"## 任务原话（逐字，不重写）", u"",
            args.brief.strip() or u"（未提供 --brief：交付方要补，别让审查者猜需求）", u""]
    out += [u"## 改了什么（diff 摘要）", u"", "```", stat.strip() or u"（无已跟踪文件改动）", "```", u""]
    if untracked.strip():
        out += [u"未跟踪文件（新增但还没 `git add`，审查时别当成漏改）：", u"",
                "\n".join(u"- `%s`" % s for s in untracked.splitlines() if s.strip()), u""]
    out += [u"## 验收标准", u"",
            acceptance or u"（未提供 --acceptance-file：那就没有「逐条核对」的依据，工单不算完整）", u""]
    out += [u"| # | 标准 | 证据（**必须贴真跑过的命令与输出摘要**） |", u"|---|---|---|"]
    items = [l.strip() for l in acceptance.splitlines() if l.strip()] if acceptance else []
    if not items:
        out.append(u"| — | （无） | 先补验收标准 |")
    for i, item in enumerate(items, 1):
        out.append(u"| %d | %s | （待填） |" % (i, item.replace(u"|", u"\\|")))
    out += [u"", u"## 验证命令（列给人/上游跑，本脚本一条都没执行）", u""]
    if args.verify_cmds:
        out += [u"- [ ] `%s`" % c for c in args.verify_cmds]
    else:
        out.append(u"- （未列出：说明「跑什么能证明它对了」这件事没人想过）")
    out += [u"", u"## 回执（子代理/审查者只填这一节，别改上面）", u""]
    out.append(u"选了哪一态：`DONE` / `CONCERNS` / `NEEDS_CONTEXT` / `BLOCKED`（划掉其余三个）")
    out.append(u"")
    out.append(u"| 状态 | 什么时候算它 | 选它之后要做什么 |")
    out.append(u"|---|---|---|")
    for name, when, then in STATES:
        out.append(u"| `%s` | %s | %s |" % (name, when, then))
    out += [u"", u"## 修复轮次（熔断用，每轮一行）", u"",
            u"| 轮次 | 发现了什么 | 改了什么 | 跑过什么 | 结果 |", u"|---|---|---|---|---|",
            u"| 1 |  |  |  |  |", u"",
            u"超过 **2 轮仍不绿** 就停：把现象、已排除项、下一步建议写回上游，"
            u"不要开第 3 轮赌一把（同 `references/code-review.md` 的自疑循环满 3 轮交回）。",
            u"", u"## diff 正文", u"", "```diff",
            "\n".join(kept) or u"（空）", "```", u""]
    if truncated:
        out.append(u"> ⚠ diff 超 %d KB 已截断，完整看：`git -C \"%s\" diff %s`"
                   % (max(1, args.max_diff_kb), root, args.base))
        out.append(u"")
    text = "\n".join(out) + "\n"

    if args.out:
        dest = os.path.abspath(args.out)
        io.open(dest, "w", encoding="utf-8", newline="\n").write(text)
        shown = dest
    else:
        sys.stdout.write(text)
        shown = u"stdout"
    print(u"工单：%s ｜ diff %d/%d 行｜脱敏 %d 处｜截断 %s"
          % (shown, len(kept), len(diff_lines), redactions, u"是" if truncated else u"否"))
    print(u"RESULT: PACKET-OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
