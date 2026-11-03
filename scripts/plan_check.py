#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把工作树脏文件清单与本轮计划清单**对账**（将作 jiangzuo）。

**为什么要有这个**（E49 实测事故）：`git add <点名文件>` **只提交点名的文件**，
计划外的脏文件**不报错、也不进提交 ⇒ 永远不会被 git 看见**；而 `ship_check`
的自净核对**只数「待交付变更数」、不比对清单**。三个环节叠在一起 ⇒
E49 收尾时才发现 `scripts/audit_graph.py` 里躺着一处**能改坏引擎的校准变异残留**
（`if not s.get("context")` → `if True`），它已经潜伏了整整一轮。

**核什么**（两件事）：
  ① **计划外脏文件** ⇒ 当场红 —— 工作树里动了、但不在本轮计划清单里的路径；
  ② **计划内未动** ⇒ 也红 —— 计划清单里写了、但工作树里**没有任何改动**的路径
     （要么从清单里划掉、要么查为什么没改 —— 两种都该是**显式决定**，不是静默放过）。

**怎么给计划清单**（两种都行，可混用）：
  · 位置参数：`python scripts/plan_check.py SKILL.md scripts/plan_check.py`
  · `--plan FILE`：一行一个路径，`#` 注释、空行跳过
  条目以 `/` 结尾视为**目录前缀**（该目录下任何改动都算计划内）。

**退出码（三态，别混 —— 与 release_consistency 同一规矩）**：
  0 = 对过了，且一致
  1 = **对过了，且不一致**（计划外脏文件 或 计划内未动）⇒ 真问题 ⇒ 提交前必须清
  2 = **没核成**（非 git 仓库 / git 不可用 / 没给计划清单）⇒ **不假绿**：
      「没给清单就没法对账」绝不能当成「对过账了」

⚠️ **它做不了 CI 检查**：CI checkout 出来的工作树**本来就是干净的**，这条闸
只能落在**提交前的本地流程**上（§24.3 的步骤 1）—— 别以为 CI 会替你看住它。

仅使用 Python 3.8+ 标准库、**不写任何文件**（只读 git 状态）。
"""
import argparse
import io
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_NOT_CHECKED = 2

CODE_LABEL = {
    "M": u"修改", "A": u"新增", "D": u"删除", "R": u"重命名",
    "C": u"复制", "?": u"未跟踪", "!": u"已忽略",
}


def read_status(repo):
    """跑 `git status --porcelain -z --untracked-files=all`。

    返回 (退出码, 输出文本)。退出码非 0 = 没核成（不是不一致）。
    用 `-z` 是因为它是 **NUL 分隔、不做路径转义**（空格/中文路径不会被引号包起来），
    重命名条目是「新路径 \\0 旧路径」两个字段。
    """
    try:
        p = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain", "-z",
             "--untracked-files=all"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except OSError as exc:
        return 127, u"git 不可用：%s" % exc
    except subprocess.TimeoutExpired:
        return 124, u"git status 超时"
    return p.returncode, p.stdout.decode("utf-8", "replace")


def parse_status_z(text):
    """把 `-z` 格式的 status 输出解析成 [(状态码, 路径, 原路径或 None)]。

    重命名/复制（R/C）条目占**两个** NUL 字段（新路径在前、旧路径在后）；
    旧路径也算"动过"——计划里写了哪一边都算对上账，两边都没写才算计划外。
    """
    entries = []
    fields = text.split("\0")
    i = 0
    while i < len(fields):
        field = fields[i]
        i += 1
        if len(field) < 4:            # 空字段或残缺条目（输出以 \0 结尾会多一个空字段）
            continue
        code = field[:2]
        path = field[3:]
        orig = None
        if code[0] in "RC" and i < len(fields):
            orig = fields[i]
            i += 1
        entries.append((code, path, orig))
    return entries


def norm_path(p):
    """清单条目归一：反斜杠→正斜杠、去 ./ 前缀、去首尾空白。"""
    p = p.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def read_plan_file(path):
    """读计划清单文件：一行一个路径，`#` 注释、空行跳过。"""
    entries = []
    with io.open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            entries.append(norm_path(line))
    return entries


def _covered(path, exact, prefixes):
    if path in exact:
        return True
    return any(path.startswith(pre) for pre in prefixes)


def reconcile(entries, plan):
    """对账。返回 (计划外条目列表, 计划内未动列表)。

    计划条目以 `/` 结尾 = 目录前缀（子树里任何改动都算计划内）。
    """
    exact = set(p for p in plan if not p.endswith("/"))
    prefixes = tuple(p for p in plan if p.endswith("/"))
    unexpected = []
    for code, path, orig in entries:
        if _covered(path, exact, prefixes):
            continue
        if orig and _covered(orig, exact, prefixes):
            continue                     # 重命名：计划写了旧路径也算对上
        unexpected.append((code, path, orig))
    missing = []
    for p in plan:
        if p in exact:
            if not any(path == p or orig == p for _, path, orig in entries):
                missing.append(p)
        else:                            # 目录前缀：子树里有任何改动就算动过
            if not any(path.startswith(p) or (orig and orig.startswith(p))
                       for _, path, orig in entries):
                missing.append(p)
    return unexpected, missing


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="计划对账（将作）：提交前把工作树脏文件与本轮计划清单对账，"
                    "计划外的脏文件当场红（E51）。")
    ap.add_argument("paths", nargs="*", metavar="路径",
                    help="本轮计划清单（也可用 --plan FILE；两种可混用）")
    ap.add_argument("--plan", metavar="FILE", help="从文件读计划清单（一行一个路径）")
    ap.add_argument("--repo", default=".", help="仓库根（默认当前目录）")
    args = ap.parse_args(argv)

    plan = [norm_path(p) for p in args.paths]
    if args.plan:
        if not os.path.isfile(args.plan):
            print(u"计划清单文件不存在：%s" % args.plan)
            print("RESULT: PLAN-NOT-CHECKED（没给清单就没法对账，绝不当成对过）")
            return EXIT_NOT_CHECKED
        plan.extend(read_plan_file(args.plan))
    plan = [p for p in plan if p]
    if not plan:
        print(u"没有计划清单就没有对账 —— 用位置参数或 --plan FILE 给出本轮要动的路径")
        print("RESULT: PLAN-NOT-CHECKED（没核成 ≠ 通过）")
        return EXIT_NOT_CHECKED

    code, out = read_status(args.repo)
    if code != 0:
        print(u"git status 没跑成（退出码 %d）：%s" % (code, out.strip() or "（无输出）"))
        print("RESULT: PLAN-NOT-CHECKED（没核成 ≠ 通过；先确认这是不是 git 仓库）")
        return EXIT_NOT_CHECKED

    entries = parse_status_z(out)
    unexpected, missing = reconcile(entries, plan)

    print(u"计划清单 %d 条 ｜ 工作树改动 %d 处" % (len(plan), len(entries)))
    if unexpected:
        print(u"\n✘ 计划外脏文件 %d 处（不在本轮计划里 —— 要么补进计划，要么还原掉）：" % len(unexpected))
        for c, path, _orig in unexpected:
            print("   [%s] %s" % (c, path))
    if missing:
        print(u"\n✘ 计划内未动 %d 处（清单里写了、工作树没改 —— 划掉或查为什么）：" % len(missing))
        for path in missing:
            print("   %s" % path)
    if not unexpected and not missing:
        print(u"✔ 工作树改动与本轮计划清单逐条对上（没有计划外的脏文件）")
        print("RESULT: PLAN-OK")
        return EXIT_OK
    print("\nRESULT: PLAN-MISMATCH（%d 处计划外 ＋ %d 处计划内未动）" % (len(unexpected), len(missing)))
    print(u"⚠️ 这条闸只在**提交前的本地流程**上（CI 的工作树本来就是干净的，CI 看不住它）")
    return EXIT_MISMATCH


if __name__ == "__main__":
    sys.exit(main())
