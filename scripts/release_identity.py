#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布产物的**身份**核验（将作 jiangzuo）。

**这个脚本要挡的是一件事：tag 指向了不属于它那个版本的 commit。**

为什么要有它（本项目的真实教训，E37）：
    E36 发 v0.70.0 时核过一句「68 tag / 68 Release 一一对应、零缺口」——**全绿**。
    但那次核验只数了**名字与数量**。E37 复核发现：
    远端 `v0.51.0` 实际指向 `d5b88e1a`（那是 **v0.66.0 的补记笔**，2026-10-22），
    而不是 v0.51.0 的代码（`d5da9f39`）。
    ⇒ 任何人 `git checkout v0.51.0` 拿到的是**别的版本**的代码，
      而「一一对应、零缺口」这句话当时是真的。

**根因**（已证实）：`scripts/release_notes.py --publish` 调 `POST /releases` 时
    ① **没带 `target_commitish`**（GitHub 默认用默认分支 main）；
    ② **不检查远端该 tag 是否已存在**。
    ⇒ 补发一个「远端还没有 tag」的版本时，GitHub 会在 main 的 HEAD 上
    **自动造出**一个同名 tag —— 名字对，内容是当时 main 的内容。
    远端 `v0.51.0` 的 `created_at`（2026-10-22T09:22:28Z）与它的 Release 的
    `created_at` **同秒** ⇒ 正是这条路径留下的。

**判据用哪条规则**：
    「tag vX.Y.Z 指向的 commit，其 subject 中**第一个**版本号必须恰好是 X.Y.Z」。

    为什么不用「第一个含该版本号的 commit」：实测本地 68 个 tag 里有 3 个
    （v0.36.1 / v0.40.0 / v0.61.0）指向的不是该版本的第一笔 —— tag 打在
    「哪一笔」取决于当时流程走到哪，**推不出来**。拿它当判据就是造一把
    会把正确历史判错的锁（E36 刚修过一个同类的）。
    而 owner 规则在本地 **68/68 成立**，且能当场抓住已知的坏例子。

用法：
    python scripts/release_identity.py --sync      # 生成/刷新真源（不手抄 sha）
    python scripts/release_identity.py --check     # 离线核验（validate 第 26 项调它）
    python scripts/release_identity.py --remote    # 核远端 tag 与 Release（需联网）
    python scripts/release_identity.py --print     # 打印身份报告

仅使用 Python 3.8+ 标准库。`--sync` / `--check` / `--print` **不联网**；
`--remote` 需要联网（`ls-remote` + GitHub API）。
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
# 仓库身份**只有一处**（E42）：owner/name 从 `scripts/repo_identity.py` 导入
# ⇒ 本文件**不再**抄一份（抄出来的副本没人核，仓库改名时会悄悄漂）。
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from repo_identity import OWNER, NAME  # noqa: E402  （必须在本目录里）

# 版本号：v0.51.0 / 0.51.0 都认；E36 这种轮次号（没有点）不认。
VER_RE = re.compile(r"\bv?(\d+\.\d+\.\d+)\b")
# CHANGELOG 的版本条目
CL_RE = re.compile(r"^##\s*\[?(\d+\.\d+\.\d+)\]?\s*[-–—]?\s*(\d{4}-\d{2}-\d{2})", re.M)

SCHEMA = 1
TRUTH_REL = os.path.join("evals", "release-identity.json")


# ---------------------------------------------------------------- 路径帮手

def truth_path(repo=REPO):
    return os.path.join(repo, "evals", "release-identity.json")


def changelog_path(repo=REPO):
    return os.path.join(repo, "CHANGELOG.md")


# ---------------------------------------------------------------- git 帮手

def git(repo, *args):
    """跑 git，输出按 UTF-8 解（Windows 默认 GBK 会炸在中文提交说明上）。"""
    p = subprocess.run(["git", "-C", repo] + list(args),
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return p.stdout.decode("utf-8", "replace")


def git_ok(repo, *args):
    return subprocess.call(["git", "-C", repo] + list(args),
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0


def in_repo(repo):
    """这个目录是不是一个能用的 git 仓库（浅克隆 / 无 tag 也要能判断）。"""
    return os.path.isdir(os.path.join(repo, ".git")) or git_ok(repo, "rev-parse", "--git-dir")


def local_tags(repo):
    """{tag: commit_sha} —— 本地 tag 指向的 commit（解引用后）。

    ⚠️ **一次** for-each-ref 拿全部，**不要每个 tag 起一个 git 进程**：
    E37 第一版那样写（每 tag 一次 `rev-list` + 一次 `show`）⇒ 8 条判据跑了
    59 秒（68 个 tag × 多次 git 进程）⇒ 改成批量后降到亚秒级。
    """
    out = git(repo, "for-each-ref",
              "--format=%(refname:short)%09%(*objectname)%09%(objectname)%09%(objecttype)",
              "refs/tags")
    res = {}
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        name = parts[0].strip()
        if not name.startswith("v"):
            continue
        peeled, direct, otype = parts[1].strip(), parts[2].strip(), parts[3].strip()
        # annotated tag：%(objectname) 是 **tag 对象**的 sha，%(*objectname) 才是 commit
        # lightweight tag：只有一行，%(objectname) 本身就是 commit
        sha = (peeled or direct) if otype == "tag" else direct
        if sha:
            res[name] = sha
    return res


def commit_meta(repo, shas):
    """{sha: (subject, date)} —— **一次** `git log --no-walk` 拿全部。

    只走给定的这些 commit（不去遍历历史）。取不到的对象会被 git 跳过。
    """
    shas = [s for s in dict.fromkeys(shas) if s]
    if not shas:
        return {}
    out = git(repo, "log", "--no-walk=unsorted", "--format=%H%x00%s%x00%cI", *shas)
    res = {}
    for line in out.split("\n"):
        if "\x00" not in line:
            continue
        sha, subj, date = line.split("\x00", 2)
        res[sha.strip()] = (subj.strip(), date.strip()[:10])
    return res


def commit_subject(repo, sha):
    return git(repo, "show", "--no-patch", "--format=%s", sha).strip()


def commit_date(repo, sha):
    return git(repo, "show", "--no-patch", "--format=%cI", sha).strip()[:10]


def owner_of(subject):
    """commit 属于哪个版本 —— subject 里**第一个**版本号；没有则 None。"""
    m = VER_RE.search(subject or "")
    return m.group(1) if m else None


def skill_version(repo=REPO):
    """`SKILL.md` frontmatter 里的 `metadata.version`（取不到则 None）。"""
    p = os.path.join(repo, "SKILL.md")
    if not os.path.isfile(p):
        return None
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    # ⚠️ **前导空白必须允许**：SKILL.md 的 frontmatter 里是「  version: x.y.z」（缩进两格）
    #   ⇒ 用 `^version:` 会**匹配不到** ⇒ 豁免失效 ⇒ 明明是"正在发的这一版"却被当成缺口。
    m = re.search(r"^[ \t]*version:[ \t]*([0-9][0-9A-Za-z.\-]*)[ \t]*$", text, re.M)
    return m.group(1) if m else None


def changelog_versions(repo):
    """CHANGELOG 里登记的版本号。"""
    p = changelog_path(repo)
    if not os.path.isfile(p):
        return []
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return CL_RE.findall(f.read())


# ---------------------------------------------------------------- 推导

def derive(repo=REPO):
    """从**本地 git 事实**推导发布身份（不手抄任何 sha）。"""
    tags = local_tags(repo)
    meta = commit_meta(repo, list(tags.values()))
    items = {}
    for t in sorted(tags):
        sha = tags[t]
        subj, date = meta.get(sha, ("", ""))
        items[t] = {
            "version": t[1:],
            "commit": sha,
            "owner": owner_of(subj),
            "date": date,
        }
    cl = [v for v, _d in changelog_versions(repo)]
    tv = set(t[1:] for t in tags)
    gaps = {
        "changelog_without_tag": sorted(set(cl) - tv),
        "tag_without_changelog": sorted(tv - set(cl)),
    }
    return {"schema": SCHEMA, "tags": items, "known_gaps": gaps}


def truth(repo=REPO):
    p = truth_path(repo)
    if not os.path.isfile(p):
        return None
    try:
        with io.open(p, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except (ValueError, IOError):
        return None


def write_truth(data, repo=REPO):
    p = truth_path(repo)
    d = os.path.dirname(p)
    if not os.path.isdir(d):
        os.makedirs(d)
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        f.write(u"\n")


# ---------------------------------------------------------------- 离线核验

def check_local(err, info, repo=REPO, truth_data=None):
    """**离线**核验发布身份。返回 True = 没发现问题。

    这一项是 validate 的第 26 项。它能核的与不能核的，分清楚：
      能核（永远能）：真源自身的自洽性、真源与 CHANGELOG 的一致性。
      能核（**本环境有完整历史与 tag 时**）：每个 tag 指向的 commit 真的属于
        那个版本（owner 规则）—— 这才是「内容」层面的核。
      不能核：**远端**的 tag 指向（`--remote` 才做，因为它要联网）。

    `truth_data` 允许调用方传入**改坏的**真源（测试用）：git 事实仍从 `repo` 取。
    默认 None ⇒ 读 `repo` 里的真源文件。

    ⚠️ **info 条数必须恒定**：有 tag 时说「核了 N 个」，无 tag 时说「这轮没跑」。
      两条路径都发**恰好一条** info ⇒ validate 的「期望 N 条信息」不会因环境而变。
    """
    problems = []

    has_tag = in_repo(repo) and bool(local_tags(repo))
    data = truth_data if truth_data is not None else truth(repo)
    if data is None:
        # ⚠️ **没有发布产物的目录不适用这一项**。
        #   validate_skill.py 也会被用来校验**别人的**最小技能目录（测试夹具、
        #   用户拷走的技能副本）⇒ 那些目录没有 tag、更没有发布产物身份台账。
        #   若无条件要求真源存在，就是一道**在逼人说假话的锁**（E36 刚修过一个同类的）。
        if not has_tag:
            info(u"发布产物的身份：本仓库没有 tag（不是发布产物）⇒ 这一项不适用")
            return True
        err(u"[发布身份] 读不到真源 %s——发布产物的身份没人守"
            % TRUTH_REL.replace("\\", "/"))
        return False
    if data.get("schema") != SCHEMA:
        err(u"[发布身份] 真源的 schema 是 %r，本脚本要的是 %d——"
            u"真源与工具不同版，先跑 --sync"
            % (data.get("schema"), SCHEMA))
        return False

    items = data.get("tags") or {}
    gaps = data.get("known_gaps") or {}
    if not items:
        err(u"[发布身份] 真源里一个 tag 都没有——发布产物身份台账是空的")
        return False

    # ① 每个条目自洽：版本号对得上、sha 合法、owner 对得上
    for tag in sorted(items):
        it = items[tag] or {}
        ver = it.get("version")
        sha = (it.get("commit") or "")
        own = it.get("owner")
        if tag != "v" + str(ver):
            problems.append(u"真源条目「%s」的 version 是 %r——键与版本号必须一致"
                            % (tag, ver))
        if not re.match(r"^[0-9a-f]{40}$", sha):
            problems.append(u"真源条目「%s」的 commit 是 %r——必须是 40 位十六进制"
                            % (tag, sha))
            continue
        if own != ver:
            problems.append(u"真源条目「%s」记的 owner 是 %r，但它的版本号是 %r"
                            % (tag, own, ver))

    # ② 真源与本地 git 事实对账（**本环境有 tag 才核**）
    have_tags = has_tag
    checked_content = 0
    if have_tags:
        actual = local_tags(repo)
        for t in sorted(set(actual) - set(items)):
            problems.append(u"本地有 tag「%s」但真源里没有——跑 --sync 刷新真源" % t)
        for t in sorted(set(items) - set(actual)):
            problems.append(u"真源里有 tag「%s」但本地没有——真源过期或本地仓库不对" % t)
        for t in sorted(set(actual) & set(items)):
            if actual[t] != items[t].get("commit"):
                problems.append(u"tag「%s」本地指向 %s，真源记的是 %s——"
                                u"真源与实物对不上（跑 --sync 核）"
                                % (t, actual[t][:7], (items[t].get("commit") or "")[:7]))
        # ③ **内容**层面的核：tag 指向的 commit 真的属于那个版本吗
        meta = commit_meta(repo, list(actual.values()))
        for t in sorted(set(actual) & set(items)):
            sha = actual[t]
            if sha not in meta:
                problems.append(u"tag「%s」指向的 commit %s 不在本仓库历史里"
                                % (t, sha[:7]))
                continue
            own = owner_of(meta[sha][0])
            checked_content += 1
            if own != t[1:]:
                problems.append(u"tag「%s」指向的 commit（%s）属于版本 %r，"
                                u"不是 %r——**tag 指错了版本**"
                                % (t, sha[:7], own, t[1:]))
    # else：本环境没有 tag —— 这不是"通过"，也不是"失败"，
    #       而是**这一轮没跑内容核**（浅克隆 / 未 fetch tags）。
    #       ⇒ 不用 err（那会让浅克隆环境变红），但要在 info 里如实说。

    # ④ CHANGELOG 与 tag 的两个差集：只许比登记的例外**更小**，不许更大
    cl = [v for v, _d in changelog_versions(repo)]
    tv = set(t[1:] for t in items)
    reg_no_tag = set(gaps.get("changelog_without_tag") or [])
    reg_no_cl = set(gaps.get("tag_without_changelog") or [])
    now_no_tag = set(cl) - tv
    now_no_cl = tv - set(cl)
    # ⚠️ **当前版本豁免**：正在发的这一版（CHANGELOG 有条目、tag 还没打）是**常态**
    #   —— tag 必须指向一个 commit ⇒ 必然是「先提交、后打 tag」⇒
    #   若不豁免，版本笔提交前 validate 必然红 ⇒ 这是一道**在逼人说假话的锁**。
    #   豁免的**只有当前版本**；历史版本漏打 tag 仍然是错。
    cur = skill_version(repo)
    if cur:
        now_no_tag.discard(cur)
    for v in sorted(now_no_tag - reg_no_tag):
        problems.append(u"版本 %s 在 CHANGELOG 里有、却没有 tag——"
                        u"新出现的发布缺口（已登记的例外：%s）"
                        % (v, u"、".join(sorted(reg_no_tag)) or u"无"))
    for v in sorted(now_no_cl - reg_no_cl):
        problems.append(u"版本 %s 有 tag、CHANGELOG 里却没有条目——"
                        u"新出现的台账缺口（已登记的例外：%s）"
                        % (v, u"、".join(sorted(reg_no_cl)) or u"无"))

    for p in problems:
        err(u"[发布身份] " + p)
    if problems:
        return False
    if checked_content:
        info(u"发布产物的身份对得上（%d 个 tag：键/版本号/sha/owner 自洽，"
             u"内容层面核了 %d 个——tag 指向的 commit 确实属于那个版本）"
             % (len(items), checked_content))
    else:
        info(u"发布产物的身份：真源 %d 个 tag 自洽，但**内容层面这轮没核**"
             u"（本环境没有 git tag——浅克隆或未 fetch tags；远端核验用 "
             u"`release_identity.py --remote`）" % len(items))
    return True


# ---------------------------------------------------------------- 远端核验

def parse_ls_remote(out):
    """`git ls-remote --tags` 的输出 → {tag: 最终指向的 commit}。

    ⚠️ annotated tag 在输出里有**两行**：
        <tag对象sha>  refs/tags/vX.Y.Z
        <commit sha>   refs/tags/vX.Y.Z^{}
    第一行是 **tag 对象**的 sha，不是 commit 的 ⇒ 必须优先取 `^{}` 那行，
    否则会把每一个 annotated tag 都误报成「指错了 commit」。
    轻量 tag 只有一行，它本身就是 commit sha。
    （E37 第一版就踩了这个：67 个 tag 全报"指错"，而真的错的只有 1 个。）
    """
    direct = {}
    peel = {}
    for line in out.split("\n"):
        if "refs/tags/" not in line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        sha = parts[0]
        name = parts[1].split("refs/tags/")[1]
        if name.endswith("^{}"):
            peel[name[:-3]] = sha
        else:
            direct[name] = sha
    res = {}
    for name, sha in direct.items():
        res[name] = peel.get(name, sha)
    for name, sha in peel.items():
        res.setdefault(name, sha)
    return res


def remote_tags(repo=REPO, token=None):
    """{tag: commit_sha} —— 远端 tag **最终指向的 commit**。

    **两条通道**：① `git ls-remote`（直、快，但依赖 **git 传输通道**）；
    ② **GitHub API**（`git/matching-refs` ＋ peel）—— git 通道不通时**自动回退**。

    为什么要有回退（E37 实测）：发布流程**只该被"远端身份对不对"卡住**，
    不该被"这台机器此刻能不能跑 git 传输"卡住 —— E37 那天 `github.com:443`
    在 **TLS 层被选择性阻断**（TCP 层可连、`ls-remote` 21 秒超时），
    而 `api.github.com` **完全正常** ⇒ 没有回退的话，那天 Release 根本发不出去
    （而"发不出去"恰恰是最该由代码而不是由网络运气决定的事）。
    """
    out = git(repo, "ls-remote", "--tags", "origin")
    if out.strip():
        return parse_ls_remote(out)
    if token:
        return remote_tags_via_api(token, repo)
    return {}


def parse_matching_refs(entries):
    """GitHub API 的 `git/matching-refs` → {tag: (object_sha, object_type)}。

    纯函数（可单测）：API 返回的每条是 `{"ref": "refs/tags/vX.Y.Z", "object": {...}}`；
    **annotated tag 的 object 是 tag 对象**（不是 commit）⇒ 还要 peel 一步。
    """
    res = {}
    for e in entries or []:
        ref = e.get("ref") or ""
        if not ref.startswith("refs/tags/"):
            continue
        obj = e.get("object") or {}
        res[ref[len("refs/tags/"):]] = (obj.get("sha"), obj.get("type"))
    return res


def peel_object(obj_json):
    """`GET /git/tags/{sha}` 的响应 → 它指向的 **commit sha**（或 None）。

    纯函数（可单测）：annotated tag → tag 对象 → 再一层才是 commit。
    """
    obj = (obj_json or {}).get("object") or {}
    if obj.get("type") == "commit":
        return obj.get("sha")
    return None


def remote_tags_via_api(token, repo=REPO):
    """{tag: commit_sha} —— **纯 API 通道**（git 传输不通时用）。

    ⚠️ `matching-refs` 默认一页 30 条 ⇒ 显式 `per_page=100`；
    若**恰好**返回 100 条则**明确报错**（不静默截断——那会变成"少核了几个 tag"）。
    """
    import urllib.request
    api = "https://api.github.com/repos/%s/%s/git/matching-refs/tags/?per_page=100" % (OWNER, NAME)
    hdr = {"Accept": "application/vnd.github+json", "User-Agent": "jiangzuo-identity"}
    if token:
        hdr["Authorization"] = "token " + token
    req = urllib.request.Request(api, headers=hdr)
    with urllib.request.urlopen(req, timeout=60) as r:
        entries = json.load(r)
    if len(entries) >= 100:
        raise RuntimeError(
            "matching-refs 返回 %d 条（>= per_page 上限）⇒ 可能有 tag 没被核到；"
            "**不静默截断**——请分页取全后再跑" % len(entries))
    refs = parse_matching_refs(entries)
    out = {}
    for name, (sha, typ) in refs.items():
        if not sha:
            continue
        if typ == "commit":
            out[name] = sha
        elif typ == "tag":
            url = "https://api.github.com/repos/%s/%s/git/tags/%s" % (OWNER, NAME, sha)
            req = urllib.request.Request(url, headers=hdr)
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    peeled = peel_object(json.load(r))
            except Exception:       # noqa: BLE001 —— 核不到就跳过，但**不假装通过**
                peeled = None
            if peeled:
                out[name] = peeled
    return out


def remote_releases(token, repo=REPO):
    """远端 Release 的 tag_name 集合（显式分页——默认只回 30 条）。"""
    import urllib.request
    api = "https://api.github.com/repos/%s/%s/releases?per_page=100" % (OWNER, NAME)
    hdr = {"Accept": "application/vnd.github+json", "User-Agent": "jiangzuo-identity"}
    if token:
        hdr["Authorization"] = "token " + token
    names = []
    page = 1
    while True:
        req = urllib.request.Request(api + "&page=%d" % page, headers=hdr)
        with urllib.request.urlopen(req, timeout=60) as r:
            batch = json.load(r)
        if not batch:
            break
        names += [x.get("tag_name") for x in batch]
        if len(batch) < 100:
            break
        page += 1
    return names


def check_remote(token=None, verbose=True, repo=REPO):
    """核**远端**的发布产物身份。返回 (problems, summary)。"""
    problems = []
    truth_data = truth(repo)
    if truth_data is None:
        return ([u"读不到真源，无法核远端"], {})
    items = truth_data.get("tags") or {}
    try:
        rt = remote_tags(repo, token)
    except Exception as e:          # noqa: BLE001 —— 核不到就如实说，不当通过
        return ([u"ls-remote 拿不到远端 tag（%s）" % e], {})
    if not rt:
        return ([u"ls-remote 拿不到远端 tag（网络或 remote 不对；"
                u"git 通道不通时应回退到 API 通道——检查 token 是否传了）"], {})

    # ① 远端 tag 集合 == 真源 tag 集合
    for t in sorted(set(rt) - set(items)):
        problems.append(u"远端有 tag「%s」但真源里没有——发布产物身份台账缺一条" % t)
    for t in sorted(set(items) - set(rt)):
        problems.append(u"真源有 tag「%s」但远端没有——tag 没推上去" % t)

    # ② **内容**一致：远端 tag 指向的 commit == 真源记的 commit
    same = 0
    for t in sorted(set(rt) & set(items)):
        want = (items[t].get("commit") or "")
        got = rt[t]
        if want and got != want:
            problems.append(u"远端 tag「%s」指向 %s，本地/真源是 %s——"
                            u"**远端的 tag 指错了 commit**" % (t, got[:7], want[:7]))
        else:
            same += 1

    # ③ Release ↔ tag 一一对应
    rel = []
    try:
        rel = remote_releases(token, repo)
    except Exception as e:          # noqa: BLE001 —— 核不到就如实说，不当通过
        problems.append(u"核不了远端 Release（%s）——这一项没跑" % e)
    if rel:
        rset = set(rel)
        tset = set(rt)
        for t in sorted(rset - tset):
            problems.append(u"远端有 Release「%s」却没有对应 tag" % t)
        for t in sorted(tset - rset):
            problems.append(u"远端有 tag「%s」却没有对应 Release" % t)

    summary = {"remote_tags": len(rt), "truth_tags": len(items),
               "same": same, "releases": len(rel)}
    if verbose:
        for p in problems:
            print(u"[发布身份/远端] " + p)
        if not problems:
            print(u"[发布身份/远端] 远端 %d 个 tag 与真源逐条同 commit（%d 个），"
                  u"Release %d 个，一一对应 ✓"
                  % (len(rt), same, len(rel)))
    return (problems, summary)


# ---------------------------------------------------------------- CLI

def do_sync(repo=REPO):
    data = derive(repo)
    old = truth(repo)
    changed = []
    if old:
        old_items = old.get("tags") or {}
        for t in set(old_items) | set(data["tags"]):
            a = (old_items.get(t) or {}).get("commit")
            b = (data["tags"].get(t) or {}).get("commit")
            if a != b:
                changed.append(t)
    data["generated_by"] = "scripts/release_identity.py --sync"
    data["owner_rule"] = ("tag vX.Y.Z 指向的 commit，其 subject 中第一个版本号"
                           "必须恰好等于 X.Y.Z")
    write_truth(data, repo)
    print("wrote %s：%d 个 tag，known_gaps 记 %d/%d 条"
          % (TRUTH_REL.replace("\\", "/"), len(data["tags"]),
             len(data["known_gaps"]["changelog_without_tag"]),
             len(data["known_gaps"]["tag_without_changelog"])))
    if changed:
        print("changed vs old truth: %s" % "、".join(sorted(changed)))
    return 0


def do_print(repo=REPO):
    data = truth(repo)
    if data is None:
        print("no truth file")
        return 1
    items = data.get("tags") or {}
    print("tags=%d  gaps=%s" % (len(items), json.dumps(data.get("known_gaps"),
                                                        ensure_ascii=False)))
    for t in sorted(items, key=lambda x: [int(p) for p in x[1:].split(".")]):
        it = items[t]
        print("  %-10s %s  owner=%-8s %s"
              % (t, (it.get("commit") or "")[:7], it.get("owner"), it.get("date")))
    return 0


def main():
    ap = argparse.ArgumentParser(description="将作：发布产物的身份核验")
    ap.add_argument("--sync", action="store_true", help="生成/刷新真源")
    ap.add_argument("--check", action="store_true", help="离线核验")
    ap.add_argument("--remote", action="store_true", help="核远端 tag 与 Release")
    ap.add_argument("--print", dest="do_print", action="store_true", help="打印身份报告")
    ap.add_argument("--token", help="GitHub token（--remote 核 Release 时需要）")
    args = ap.parse_args()
    if args.sync:
        return do_sync()
    if args.remote:
        problems, _summary = check_remote(args.token)
        return 1 if problems else 0
    if args.check:
        problems = []

        def err(msg):
            problems.append(msg)
            print(msg)

        def info(msg):
            print(msg)

        ok = check_local(err, info)
        return 0 if ok else 1
    if args.do_print:
        return do_print()
    ap.print_help()
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:      # Python < 3.7
        pass
    sys.exit(main())
