#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库身份（owner / name / 各种 URL）的**唯一**机器可读出处（E42）。

为什么单独立这一个文件（E41 复核时记下的欠账）：
这个身份此前**抄在四个脚本里**（`release_identity.py` / `release_consistency.py` /
`release_notes.py` / `audit_scan.py` 的 SARIF 链接）⇒ 仓库搬家或改名时**必然漂**，
而漂了没人发现 —— 三个地方各自发版、各自指向不同的仓库，**没有任何东西会对账它们**。
⇒ 收进一处，其余**从这儿导入**；第 7 项的判据会盯住
「**身份在 `scripts/` 里只许出现在这一个文件**」。

⚠️ **别的脚本请从这里导入，不要再抄一份** —— 抄出来的副本没人核，
这正是本轮要消灭的那件事。

⚠️ **不给"脚本被单独拷走"兜底一份副本**：兜底副本就是第二真源 ⇒ 与本文件的存在
理由相反 ⇒ 宁可**直接报错**（脚本目录不在 `sys.path` 时 import 失败）。
"""
OWNER = "Zhang-jx00"
NAME = "jiangzuo"
REPO = OWNER + "/" + NAME
REPO_URL = "https://github.com/" + REPO
CLONE_URL = REPO_URL + ".git"
