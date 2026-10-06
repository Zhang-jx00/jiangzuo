#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目摸底扫描器 —— 将作 (jiangzuo)

扫描项目目录，自动识别技术栈、目录结构、构建/测试配置，
输出一份项目摸底档案（project-profile）的 Markdown 草稿，
其中人工才能回答的部分留空待补。

用法:
    python project_scan.py [项目目录] [--out 输出文件.md]

会做：识别清单文件/锁文件/关键文件与环境变量名、摘录 README 开头、
      推断技术栈与常用命令，产出待人工补充的摸底档案草稿。
不会做：运行项目、执行测试、猜测调用链、读取 .env 的真实值（只读 .env.example）。

仅使用 Python 标准库（3.8+），不联网、不修改项目文件。
"""
import argparse
import io
import json
import os
import re
import sys
from datetime import date

# 常见框架名 -> 人类可读名称（用于从依赖里猜框架）
FRAMEWORK_HINTS = {
    "react": "React", "vue": "Vue", "svelte": "Svelte", "angular": "Angular",
    "next": "Next.js", "nuxt": "Nuxt", "vite": "Vite", "webpack": "Webpack",
    "tailwindcss": "Tailwind CSS", "element-plus": "Element Plus",
    "antd": "Ant Design", "element-ui": "Element UI", "arco-design": "Arco Design",
    "express": "Express", "koa": "Koa", "nest": "NestJS", "egg": "Egg",
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask", "tornado": "Tornado",
    "sqlalchemy": "SQLAlchemy", "alembic": "Alembic", "celery": "Celery",
    "spring-boot": "Spring Boot", "gin": "Gin", "beego": "Beego",
    "actix-web": "Actix Web", "axum": "Axum", "rails": "Rails", "laravel": "Laravel",
    "flutter": "Flutter", "electron": "Electron", "tauri": "Tauri",
}

SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".idea", ".vscode", "dist", "build", "out", "target", "vendor",
    ".next", ".nuxt", "coverage", ".pytest_cache", ".mypy_cache", ".tox",
    "site-packages", ".gradle", "bin", "obj", "Pods", ".dart_tool",
}

MANIFESTS = [
    "package.json", "pyproject.toml", "requirements.txt", "go.mod",
    "pom.xml", "build.gradle", "build.gradle.kts", "Cargo.toml",
    "composer.json", "Gemfile", "mix.exs", "pubspec.yaml",
]

KEY_FILES = [
    "README.md", "readme.md", "Dockerfile", "docker-compose.yml",
    "docker-compose.yaml", "Makefile", ".env.example", "env.example",
    "pytest.ini", "tox.ini", "vitest.config.ts", "vitest.config.js",
    "jest.config.js", "jest.config.ts", "alembic.ini", "prisma/schema.prisma",
    "tsconfig.json", ".eslintrc", ".eslintrc.js", "eslint.config.js",
    "prettier.config.js", "CHANGELOG.md", "LICENSE",
]

TEXT_READ_LIMIT = 200_000  # 每个清单文件最多读 200KB，防大文件


def read_text(path, limit=TEXT_READ_LIMIT):
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def detect_frameworks(text):
    """在依赖文本（小写）里找已知框架名。"""
    found = []
    for key, name in FRAMEWORK_HINTS.items():
        # 边界匹配，避免 react 撞上 react-native-fetch 之类的误报方向反过来也一样
        if re.search(r'["\']%s["\']|["\']@%s/|%s[=@>\s~]' % (key, key, key), text):
            found.append(name)
    return found


def scan_package_json(root):
    p = os.path.join(root, "package.json")
    text = read_text(p)
    if not text:
        return None
    info = {"name": "", "scripts": [], "frameworks": [], "deps": 0}
    try:
        data = json.loads(text)
        info["name"] = data.get("name", "")
        deps = {}
        deps.update(data.get("dependencies", {}) or {})
        deps.update(data.get("devDependencies", {}) or {})
        info["deps"] = len(deps)
        info["frameworks"] = detect_frameworks(json.dumps(deps, ensure_ascii=False).lower())
        scripts = data.get("scripts", {}) or {}
        for key in ("dev", "start", "build", "test", "lint", "preview"):
            if key in scripts:
                info["scripts"].append("`npm run %s` → `%s`" % (key, scripts[key]))
    except (ValueError, AttributeError):
        info["note"] = "package.json 解析失败，请人工查看"
    return info


def scan_python_project(root):
    info = None
    pyproject = os.path.join(root, "pyproject.toml")
    reqs = os.path.join(root, "requirements.txt")
    if os.path.isfile(pyproject):
        text = read_text(pyproject)
        m = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', text, re.M)
        info = {"name": m.group(1) if m else "",
                "frameworks": detect_frameworks(text.lower()), "deps": None}
        m = re.search(r'^\s*(?:dependencies|requires)\s*=\s*\[(.*?)\]', text, re.S | re.M)
        if m:
            info["deps"] = len(re.findall(r'["\'][^"\']+["\']', m.group(1)))
    elif os.path.isfile(reqs):
        text = read_text(reqs)
        lines = [ln.strip() for ln in text.splitlines()
                 if ln.strip() and not ln.strip().startswith("#")]
        info = {"name": "", "deps": len(lines),
                "frameworks": detect_frameworks(text.lower())}
    if info:
        cmds = []
        for makefile, cmd in (("Makefile", "make %s"),):
            pass
        if os.path.isfile(os.path.join(root, "manage.py")):
            cmds.append("`python manage.py runserver`（Django 猜测）")
        return info
    return None


def scan_go_mod(root):
    p = os.path.join(root, "go.mod")
    text = read_text(p)
    if not text:
        return None
    m = re.search(r"^module\s+(\S+)", text, re.M)
    return {"name": m.group(1) if m else "",
            "frameworks": detect_frameworks(text.lower()), "deps": text.count("\t")}


def scan_other_manifests(root):
    for name in ("Cargo.toml", "composer.json", "Gemfile", "mix.exs", "pubspec.yaml",
                 "pom.xml", "build.gradle", "build.gradle.kts"):
        if os.path.isfile(os.path.join(root, name)):
            text = read_text(os.path.join(root, name)).lower()
            return {"name": name, "frameworks": detect_frameworks(text), "deps": None}
    return None


def list_top_dirs(root):
    dirs = []
    try:
        for entry in sorted(os.listdir(root)):
            full = os.path.join(root, entry)
            if os.path.isdir(full) and entry not in SKIP_DIRS and not entry.startswith("."):
                dirs.append(entry)
    except OSError:
        pass
    return dirs[:25]


def find_key_files(root):
    found = []
    seen = set()
    for name in KEY_FILES:
        if os.path.isfile(os.path.join(root, name)):
            real = os.path.basename(os.path.realpath(os.path.join(root, name)))
            if real.lower() in seen:
                continue  # Windows 大小写不敏感会重复命中
            seen.add(real.lower())
            found.append(real)
    workflows = os.path.join(root, ".github", "workflows")
    if os.path.isdir(workflows):
        try:
            ymls = [f for f in sorted(os.listdir(workflows)) if f.endswith((".yml", ".yaml"))]
            if ymls:
                found.append(".github/workflows/ (" + ", ".join(ymls) + ")")
        except OSError:
            pass
    migrations = [d for d in ("migrations", "alembic", "prisma/migrations", "db/migrate")
                  if os.path.isdir(os.path.join(root, d))]
    for m in migrations:
        found.append(m + "/ (数据库迁移目录)")
    tests = [d for d in ("tests", "test", "__tests__", "spec") if os.path.isdir(os.path.join(root, d))]
    for t in tests:
        found.append(t + "/ (测试目录)")
    return found


LOCKFILES = {
    "pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "package-lock.json": "npm",
    "poetry.lock": "poetry", "uv.lock": "uv", "Pipfile.lock": "pipenv",
    "Cargo.lock": "cargo", "go.sum": "go modules", "composer.lock": "composer",
    "Gemfile.lock": "bundler",
}


def detect_pkg_manager(root):
    for lock, mgr in LOCKFILES.items():
        if os.path.isfile(os.path.join(root, lock)):
            return mgr
    return None


def parse_env_example(root):
    for name in (".env.example", "env.example", ".env.sample", ".env.template"):
        p = os.path.join(root, name)
        if os.path.isfile(p):
            text = read_text(p)
            vars_ = []
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                var = line.split("=", 1)[0].strip()
                if var and not var.startswith(" "):
                    vars_.append(var)
            return name, vars_
    return None, []


def readme_excerpt(root):
    for name in ("README.md", "readme.md", "README.rst", "README"):
        p = os.path.join(root, name)
        if os.path.isfile(p):
            lines = read_text(p, 8000).splitlines()[:18]
            return "\n".join(lines)
    return "_（未找到 README）_"


def build_report(root):
    root = os.path.abspath(root)
    name = os.path.basename(root)
    pkg = scan_package_json(root)
    py = scan_python_project(root)
    go = scan_go_mod(root)
    other = scan_other_manifests(root)
    stack_rows = []
    if pkg:
        stack_rows.append(("Node.js / package.json", pkg["name"] or "-", pkg["deps"]))
        if pkg["frameworks"]:
            stack_rows.append(("前端/框架（由依赖推断）", "、".join(pkg["frameworks"]), ""))
    if py:
        stack_rows.append(("Python / " + ("pyproject.toml" if os.path.isfile(os.path.join(root, "pyproject.toml")) else "requirements.txt"),
                           py["name"] or "-", py["deps"]))
        if py["frameworks"]:
            stack_rows.append(("框架（由依赖推断）", "、".join(py["frameworks"]), ""))
    if go:
        stack_rows.append(("Go / go.mod", go["name"], ""))
        if go["frameworks"]:
            stack_rows.append(("框架（由依赖推断）", "、".join(go["frameworks"]), ""))
    if other:
        stack_rows.append((other["name"], "-", ""))
        if other["frameworks"]:
            stack_rows.append(("框架（由依赖推断）", "、".join(other["frameworks"]), ""))
    if not stack_rows:
        stack_rows.append(("未识别", "未找到常见清单文件（package.json / pyproject.toml / go.mod …）", ""))

    scripts_md = "\n".join("- " + s for s in (pkg or {}).get("scripts", [])) or "- （未从 package.json 读到 scripts）"
    dirs_md = "\n".join("- `%s/` — ？？（人工补一句职责）" % d for d in list_top_dirs(root)) or "- （空）"
    keys_md = "\n".join("- %s" % k for k in find_key_files(root)) or "- （未发现）"

    mgr = detect_pkg_manager(root)
    env_name, env_vars = parse_env_example(root)
    extra_md = ""
    if mgr:
        extra_md += "\n## 包管理器（由锁文件判定）\n\n- %s\n" % mgr
    if env_name:
        shown = "`%s`" % "`、`".join(env_vars[:15]) if env_vars else "（空文件）"
        more = " ……共 %d 个" % len(env_vars) if len(env_vars) > 15 else ""
        extra_md += "\n## 环境变量（来自 %s）\n\n- %s%s\n- 每个变量的用途与取值方式：？？\n" % (env_name, shown, more)

    return u"""# 项目摸底档案（草稿）：{name}

> 生成日期：{date} ｜ 生成方式：scripts/project_scan.py 自动扫描 + 人工补充
> 使用说明：所有 "？？" 处需要人工确认后替换；本文件落盘到 docs/jiangzuo/profiles/ 后随项目维护。

## 一句话认知

？？（这个项目是做什么的、给谁用、当前状态）

## 技术栈

| 项 | 值 | 备注 |
|---|---|---|
{stack_rows}

## scripts / 常用命令（来自 package.json）

{scripts}

## 顶层目录职责

{dirs}

## 发现的关键文件

{keys}
{extra}
## README 开头（原文摘录）

```
{readme}
```

## 人工补充区（扫描器答不了的，逐项填写）

- 启动开发环境的完整命令：？？
- 运行测试的完整命令：？？（建议立即跑一次，记录基线：__ passed / __ failed）
- 构建命令：？？
- 代码分层模式：？？（如 controller → service → repository）
- 一条关键调用链（入口 → 业务 → 数据）：？？
- 项目惯例（命名/错误处理/测试写法各一条）：？？
- 待确认问题：
  1. ？？
  2. ？？
""".format(name=name, date=date.today().isoformat(),
               stack_rows="\n".join("| %s | %s | %s |" % r for r in stack_rows),
               scripts=scripts_md, dirs=dirs_md, keys=keys_md, extra=extra_md,
               readme=readme_excerpt(root))


def main():
    parser = argparse.ArgumentParser(
        description="项目摸底扫描器（将作）：自动识别技术栈与结构，生成摸底档案草稿。")
    parser.add_argument("path", nargs="?", default=".", help="项目目录（默认当前目录）")
    parser.add_argument("--out", default=None, help="输出到文件（默认打印到终端）")
    args = parser.parse_args()

    if not os.path.isdir(args.path):
        print("错误：目录不存在：%s" % args.path, file=sys.stderr)
        return 2
    report = build_report(args.path)
    if args.out:
        out_path = os.path.abspath(args.out)
        out_dir = os.path.dirname(out_path)
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        with io.open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        print("已生成摸底档案草稿：%s" % out_path)
        print("下一步：人工填写『人工补充区』的 ？? 项，然后按 onboarding.md 完成摸底。")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
