#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档生成器 —— 将作 (jiangzuo)

从技能内置模板在项目里生成规范落盘的文档骨架，统一落到 docs/jiangzuo/ 下，
避免手写路径和格式漂移。

用法:
    python new_doc.py <类型> <标题> [--dir 项目根] [--force]

类型与落盘位置:
    plan       任务计划     → docs/jiangzuo/plans/YYYY-MM-DD-<标题>.md
    testplan   测试计划     → docs/jiangzuo/plans/YYYY-MM-DD-<标题>-test-plan.md
    brief      需求简报     → docs/jiangzuo/briefs/YYYY-MM-DD-<标题>.md
    profile    项目摸底档案 → docs/jiangzuo/profiles/YYYY-MM-DD-<标题>.md
    adr        架构决策记录 → docs/jiangzuo/adr/ADR-<NNN>-<标题>.md（自动编号）
    contract   接口契约     → docs/jiangzuo/contracts/<标题>.md
    bug        缺陷报告     → docs/jiangzuo/reports/YYYY-MM-DD-bug-<标题>.md
    postmortem 事故复盘     → docs/jiangzuo/reports/YYYY-MM-DD-postmortem-<标题>.md
    release    发布检查单   → docs/jiangzuo/reports/YYYY-MM-DD-release-<标题>.md
    progress   进度报告     → docs/jiangzuo/reports/YYYY-MM-DD-progress-<标题>.md
    delivery   交付报告     → docs/jiangzuo/reports/YYYY-MM-DD-delivery-<标题>.md
    debt       技术债登记   → docs/jiangzuo/debts/tech-debt.md（唯一登记簿，已存在则提示追加）

仅使用 Python 标准库（3.8+）。
"""
import argparse
import io
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.normpath(os.path.join(HERE, "..", "templates"))

# 类型 -> (模板文件, 落盘子目录, 文件名格式, 是否日期前缀)
TYPES = {
    "plan":       ("task-plan.md",         "plans",    "{slug}",            True),
    "testplan":   ("test-plan.md",         "plans",    "{slug}-test-plan",  True),
    "brief":      ("requirement-brief.md", "briefs",   "{slug}",            True),
    "profile":    ("project-profile.md",   "profiles", "{slug}",            True),
    "adr":        ("adr.md",               "adr",      "ADR-{nnn}-{slug}",  False),
    "contract":   ("api-contract.md",      "contracts", "{slug}",           False),
    "bug":        ("bug-report.md",        "reports",  "bug-{slug}",        True),
    "postmortem": ("postmortem.md",        "reports",  "postmortem-{slug}", True),
    "release":    ("release-checklist.md", "reports",  "release-{slug}",    True),
    "progress":   ("progress-report.md",   "reports",  "progress-{slug}",   True),
    "delivery":   ("delivery-report.md",   "reports",  "delivery-{slug}",   True),
    "debt":       ("tech-debt.md",         "debts",    "tech-debt",         False),
}


def slugify(title):
    """保留中文字符，替换文件系统非法字符，空格转连字符。"""
    slug = re.sub(r'[\\/:*?"<>|\r\n\t]', "-", title.strip())
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "untitled"


def next_adr_number(adr_dir):
    existing = []
    if os.path.isdir(adr_dir):
        for fn in os.listdir(adr_dir):
            m = re.match(r"ADR-(\d+)-", fn)
            if m:
                existing.append(int(m.group(1)))
    return max(existing) + 1 if existing else 1


def render(text, mapping):
    for key, value in mapping.items():
        text = text.replace("{{%s}}" % key, value)
    return text


def main():
    parser = argparse.ArgumentParser(
        description="文档生成器（将作）：按模板在项目 docs/jiangzuo/ 下生成规范文档骨架。")
    parser.add_argument("type", help="文档类型：%s" % " / ".join(TYPES))
    parser.add_argument("title", help="文档标题（用于文件名与 {{TITLE}} 占位符）")
    parser.add_argument("--dir", default=".", help="项目根目录（默认当前目录）")
    parser.add_argument("--force", action="store_true", help="目标文件已存在时覆盖")
    args = parser.parse_args()

    t = args.type.lower()
    if t not in TYPES:
        print("错误：未知类型 %r。可选：%s" % (args.type, " / ".join(TYPES)), file=sys.stderr)
        return 2
    template_name, subdir, name_fmt, dated = TYPES[t]

    template_path = os.path.join(TEMPLATE_DIR, template_name)
    if not os.path.isfile(template_path):
        print("错误：找不到模板 %s（技能目录可能不完整）" % template_path, file=sys.stderr)
        return 2

    project_root = os.path.abspath(args.dir)
    if not os.path.isdir(project_root):
        print("错误：项目目录不存在：%s" % project_root, file=sys.stderr)
        return 2

    out_dir = os.path.join(project_root, "docs", "jiangzuo", subdir)
    os.makedirs(out_dir, exist_ok=True)

    slug = slugify(args.title)
    nnn = ""
    if t == "adr":
        nnn = "%03d" % next_adr_number(out_dir)
    filename = name_fmt.format(slug=slug, nnn=nnn)
    if dated:
        filename = "%s-%s" % (date.today().isoformat(), filename)
    out_path = os.path.join(out_dir, filename + ".md")

    if os.path.exists(out_path):
        if t == "debt" and not args.force:
            print("技术债登记簿已存在：%s" % os.path.relpath(out_path, project_root))
            print("下一步：直接在表格末尾追加一行（登记簿唯一，不要另开新档）。")
            return 0
        if not args.force:
            print("错误：文件已存在（不加 --force 不覆盖）：%s" % out_path, file=sys.stderr)
            return 2

    with io.open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = render(content, {
        "TITLE": args.title.strip(),
        "DATE": date.today().isoformat(),
        "PROJECT_NAME": os.path.basename(project_root),
        "NNN": nnn,
        "TYPE": t,
    })

    with io.open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("已生成：%s" % os.path.relpath(out_path, project_root))
    hints = {
        "plan": "下一步：填『全局约束』与任务清单；每完成一步勾一个 checkbox。",
        "brief": "下一步：与用户逐条确认『验收标准』后，把状态改为『已确认』。",
        "adr": "下一步：把备选方案的取舍写完整，状态改为『已接受』。",
        "contract": "下一步：契约确认后通知前后端；接口变更必须回写『联调记录』。",
        "debt": "下一步：按表格列追加技术债条目；本文件是唯一登记簿，不要另开新档。",
        "postmortem": "下一步：行动项逐条给负责人和期限，并落进任务计划。",
        "delivery": "下一步：四问必须附真实验证证据，不留『已自测』三个字。",
    }
    if t in hints:
        print(hints[t])
    return 0


if __name__ == "__main__":
    sys.exit(main())
