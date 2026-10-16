#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计链验收夹具生成器 —— 将作 (jiangzuo)

生成一份**已知答案**的多语言语料：一半是植入的漏洞（must find），
一半是写对了的对照样本（must not find），外加可选的良性填充文件用于测内存曲线。
答案清单 expected.json 由本脚本按真实行号算出（probe 子串定位），不手填行号。

用法:
    python gen_corpus.py --out DIR [--fillers N]

为什么放在 evals/ 而不是把漏洞代码直接提交进仓库：语料只在评测时物化，
公开仓库里不留"看起来像后门"的文件；评测运行目录默认在仓库外。

仅使用 Python 标准库（3.8+）。
"""
import argparse
import io
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------- 植入漏洞（must find）
VULN = {
    "vuln_py_sql.py": (
        "from flask import request, Flask\n"
        "import sqlite3\n"
        "app = Flask(__name__)\n\n"
        "@app.route(\"/search\")\n"
        "def search():\n"
        "    q = request.args[\"q\"]\n"
        "    con = sqlite3.connect(\"app.db\")\n"
        "    return con.execute(f\"SELECT * FROM items WHERE name LIKE {q}\").fetchall()\n"),
    "vuln_py_cmd.py": (
        "from flask import request\n"
        "import os\n\n\n"
        "def run_convert(fmt):\n"
        "    name = request.args[\"name\"]\n"
        "    os.system(\"convert \" + name + \" out.\" + fmt)\n"),
    "vuln_py_path.py": (
        "from flask import request\n"
        "import os\n\n\n"
        "def read_doc():\n"
        "    f = request.args[\"file\"]\n"
        "    base = \"/srv/docs/\"\n"
        "    data = open(base + f).read()\n"
        "    return data\n"),
    "vuln_py_ssrf.py": (
        "from flask import request\n"
        "import requests\n\n\n"
        "def fetch():\n"
        "    resp = requests.get(request.args[\"url\"])\n"
        "    return resp.text\n"),
    "vuln_py_deser.py": (
        "from flask import request\n"
        "import pickle\n\n\n"
        "def ingest():\n"
        "    obj = pickle.loads(request.data)\n"
        "    return obj\n"),
    "vuln_py_eval.py": (
        "from flask import request\n\n\n"
        "def calc():\n"
        "    total = eval(request.args[\"expr\"])\n"
        "    return total\n"),
    "vuln_py_tpl.py": (
        "from flask import request, render_template_string\n\n\n"
        "def preview():\n"
        "    html = render_template_string(request.args[\"tpl\"])\n"
        "    return html\n"),
    "vuln_py_redir.py": (
        "from flask import request, redirect\n\n\n"
        "def login_next():\n"
        "    resp = redirect(request.args[\"next\"])\n"
        "    return resp\n"),
    "vuln_py_secret.py": (
        "import boto3\n\n"
        "AWS_SECRET_ACCESS_KEY = \"wJalrXUtnFEMI/K7MDENG/bPxRfiCY7f3a\"\n\n\n"
        "def client():\n"
        "    return boto3.client(\"s3\")\n"),
    "vuln_py_authgap.py": (
        "from flask import Flask\n"
        "app = Flask(__name__)\n\n"
        "@app.route(\"/admin/export\")\n"
        "def export_all():\n"
        "    return \"csv\"\n"),
    "vuln_js_sql.js": (
        "const express = require(\"express\")\n"
        "const db = require(\"./db\")\n"
        "const router = express.Router()\n\n"
        "router.get(\"/u\", async (req, res) => {\n"
        "  const rows = await db.query(`SELECT * FROM users WHERE id = ${req.query.id}`)\n"
        "  res.json(rows)\n"
        "})\n"),
    "vuln_js_cmd.js": (
        "const { execSync } = require(\"child_process\")\n"
        "const router = require(\"express\").Router()\n\n"
        "router.post(\"/thumb\", (req, res) => {\n"
        "  const out = execSync(\"convert \" + req.body.name)\n"
        "  res.send(out)\n"
        "})\n"),
    "vuln_js_xss.jsx": (
        "function Note({ data }) {\n"
        "  return <div dangerouslySetInnerHTML={{ __html: data.body }} />\n"
        "}\n"
        "export default Note\n"),
    "vuln_java_sql.java": (
        "import javax.persistence.EntityManager;\n\n"
        "public class UserDao {\n"
        "    public Object find(EntityManager em, String raw) {\n"
        "        String id = request.getParameter(\"id\");\n"
        "        return em.createNativeQuery(\"SELECT * FROM users WHERE id = \" + id)\n"
        "                .getSingleResult();\n"
        "    }\n"
        "}\n"),
    "vuln_php_sql.php": (
        "<?php\n"
        "$conn = mysqli_connect(\"localhost\", \"u\", \"p\", \"db\");\n"
        "$sql = \"SELECT * FROM posts WHERE id = \" . $_GET[\"id\"];\n"
        "$res = mysqli_query($conn, \"SELECT * FROM posts WHERE id = \" . $_GET[\"id\"]);\n"
    ),
    "vuln_py_weak.py": (
        "from flask import request\n"
        "import hashlib\n\n\n"
        "def store(password):\n"
        "    return hashlib.md5(password.encode()).hexdigest()\n"),
    # E1：DVWA 的 cryptography / javascript 两个模块逼出来的两条规则，语料侧也要有正反样本，
    # 否则新规则只有单测与靶场两处证据，CI 里滑坡了没人知道。形状取自真实 DVWA 源码。
    "vuln_php_ecb.php": (
        "<?php\n"
        "function enc($plaintext, $key) {\n"
        "    return openssl_encrypt($plaintext, 'aes-128-ecb', $key, OPENSSL_RAW_DATA);\n"
        "}\n"),
    "vuln_php_xor.php": (
        "<?php\n"
        "function xor_this($cleartext, $key) {\n"
        "    $outText = '';\n"
        "    for ($i = 0; $i < strlen($cleartext);) {\n"
        "        $outText .= $cleartext[$i] ^ $key[$i % strlen($key)];\n"
        "    }\n"
        "    return $outText;\n"
        "}\n"),
    "vuln_js_token.js": (
        "function generate_token() {\n"
        "    var phrase = document.getElementById('phrase').value;\n"
        "    document.getElementById('token').value = md5(rot13(phrase));\n"
        "}\n"),
    "vuln_js_packed.js": (
        "var table = ['token', 'value'];\n"
        "eval(function (p, a, c, k, e, d) { return p; }('0|1', 2, 2, 'a|b'.split('|'), 0, {}));\n"),
}

# ---------------------------------------------------------------- 对照样本（must not find）
SAFE = {
    "safe_py_sql.py": (
        "from flask import request\n"
        "import sqlite3\n\n\n"
        "def by_id(con):\n"
        "    uid = request.args[\"id\"]\n"
        "    return con.execute(\"SELECT * FROM t WHERE id=%s\", (uid,)).fetchall()\n"),
    "safe_py_cmd.py": (
        "import subprocess\n\n\n"
        "def convert(src, dst):\n"
        "    subprocess.run([\"convert\", src, dst], check=True)\n"),
    "safe_py_path.py": (
        "from flask import request\n"
        "import os\n\n\n"
        "ROOT = \"/srv/docs\"\n\n\n"
        "def read_doc():\n"
        "    safe_name = os.path.basename(request.args[\"file\"])\n"
        "    with open(os.path.join(ROOT, safe_name)) as fh:\n"
        "        return fh.read()\n"),
    "safe_py_ssrf.py": (
        "import requests\n"
        "from urllib.parse import urlparse\n\n"
        "ALLOWED_HOSTS = {\"api.example.com\"}\n\n\n"
        "def fetch(fetch_url):\n"
        "    if urlparse(fetch_url).hostname not in ALLOWED_HOSTS:\n"
        "        raise ValueError(\"host not allowed\")\n"
        "    return requests.get(fetch_url, timeout=5)\n"),
    "safe_py_deser.py": (
        "import yaml\n\n\ndef load(text):\n"
        "    return yaml.safe_load(text)\n"),
    "safe_py_eval.py": (
        "import ast\n\n\ndef calc(expr):\n"
        "    return ast.literal_eval(expr)\n"),
    "safe_py_redir.py": (
        "from flask import request, redirect\n\n"
        "ALLOW_HOSTS = {\"my.site\"}\n\n\n"
        "def login_next():\n"
        "    target = request.args[\"next\"]\n"
        "    if not target.startswith(\"/\"):\n"
        "        return redirect(\"/\")\n"
        "    return redirect(target)\n"),
    "safe_py_secret.py": (
        "import os\n\n"
        "API_TOKEN = os.environ[\"API_TOKEN\"]\n\n\n"
        "def token():\n"
        "    return API_TOKEN\n"),
    "safe_py_authgap.py": (
        "from flask import Flask\n"
        "from flask_login import login_required\n"
        "app = Flask(__name__)\n\n"
        "@login_required\n"
        "@app.route(\"/admin/stats\")\n"
        "def stats():\n"
        "    return \"ok\"\n"),
    "safe_py_hash.py": (
        "import hashlib\n\n\n"
        "def store(password):\n"
        "    return hashlib.sha256(password.encode()).hexdigest()\n"),
    "safe_js_sql.js": (
        "const db = require(\"./db\")\n\n\n"
        "async function byId(id) {\n"
        "  return db.query(\"SELECT * FROM users WHERE id = $1\", [id])\n"
        "}\n"),
    "safe_js_cmd.js": (
        "const { execFile } = require(\"child_process\")\n\n\n"
        "function listing(dir, cb) {\n"
        "  execFile(\"/bin/ls\", [dir], cb)\n"
        "}\n"),
    "safe_js_xss.jsx": (
        "function Note({ data }) {\n"
        "  return <div>{data.body}</div>\n"
        "}\n"
        "export default Note\n"),
    "safe_java_sql.java": (
        "import java.sql.Connection;\nimport java.sql.PreparedStatement;\n\n"
        "public class UserDao {\n"
        "    public void bind(Connection conn, String id) throws Exception {\n"
        "        PreparedStatement ps = conn.prepareStatement(\"SELECT * FROM users WHERE id = ?\");\n"
        "        ps.setString(1, id);\n"
        "        ps.executeUpdate();\n"
        "    }\n"
        "}\n"),
    "safe_php_sql.php": (
        "<?php\n"
        "$pdo = new PDO($dsn, $user, $pass);\n"
        "$stmt = $pdo->prepare(\"SELECT * FROM posts WHERE id = ?\");\n"
        "$stmt->execute([$_GET[\"id\"]]);\n"
    ),
    "safe_php_cipher.php": (
        "<?php\n"
        "$iv = random_bytes(12);\n"
        "$ct = openssl_encrypt($plaintext, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv);\n"
        "$box = sodium_crypto_secretbox($plaintext, $nonce, $key);\n"
    ),
    "safe_js_token.js": (
        "fetch('/api/csrf').then(function (r) { return r.json(); }).then(function (d) {\n"
        "    document.getElementById('token').value = d.csrf_token;\n"
        "});\n"
        "function render(name) {\n"
        "    var out = '';\n"
        "    for (var i = 0; i < name.length; i++) { out += name[i]; }\n"
        "    return out;\n"
        "}\n"),
    "manifest.txt": "本语料由 evals/audit-fixtures/gen_corpus.py 生成，答案见 expected.json\n",
}

DEPS = {
    "requirements.txt": "flask==2.3.3\nrequests==2.28.1\npyyaml==5.3\n",
    "package.json": "{\"name\": \"bench\", \"dependencies\": {\"express\": \"^4.19.2\"}}\n",
}

# (文件, 规则 id, probe 子串) —— probe 用来在写出的文件里定位真实行号
MUST_FIND = [
    ("vuln_py_sql.py", "JZ-SQLI-001", "SELECT * FROM items WHERE name LIKE"),
    ("vuln_py_cmd.py", "JZ-CMDI-001", "os.system"),
    ("vuln_py_path.py", "JZ-TRAVERSAL-001", "open(base + f)"),
    ("vuln_py_ssrf.py", "JZ-SSRF-001", "requests.get(request.args"),
    ("vuln_py_deser.py", "JZ-DESER-001", "pickle.loads"),
    ("vuln_py_eval.py", "JZ-CODE-001", "eval(request.args"),
    ("vuln_py_tpl.py", "JZ-TPLI-001", "render_template_string"),
    ("vuln_py_redir.py", "JZ-REDIR-001", "redirect(request.args"),
    ("vuln_py_secret.py", "JZ-SECRET-001", "AWS_SECRET_ACCESS_KEY"),
    ("vuln_py_authgap.py", "JZ-AUTHGAP-001", "/admin/export"),
    ("vuln_js_sql.js", "JZ-SQLI-002", "${req.query.id}"),
    ("vuln_js_cmd.js", "JZ-CMDI-001", "execSync"),
    ("vuln_js_xss.jsx", "JZ-XSS-001", "dangerouslySetInnerHTML"),
    ("vuln_java_sql.java", "JZ-SQLI-003", "createNativeQuery"),
    ("vuln_php_sql.php", "JZ-SQLI-003", "mysqli_query"),
    ("vuln_py_weak.py", "JZ-CRYPTO-001", "hashlib.md5"),
    ("vuln_php_ecb.php", "JZ-CRYPTO-003", "'aes-128-ecb'"),
    ("vuln_php_xor.php", "JZ-CRYPTO-003", "$outText .= $cleartext[$i] ^"),
    ("vuln_js_token.js", "JZ-JSINSEC-001", "= md5(rot13(phrase))"),
    ("vuln_js_packed.js", "JZ-JSINSEC-001", "eval(function ("),
    # 打包器用的就是 eval —— JZ-CODE-001（动态执行）同行命中是真阳性，答案要跟着事实走，
    # 不是把发现压掉。
    ("vuln_js_packed.js", "JZ-CODE-001", "eval(function ("),
    ("requirements.txt", "JZ-DEP-002", "pyyaml==5.3"),
    ("requirements.txt", "JZ-DEP-005", "requests==2.28.1"),
]

MUST_NOT_FIND = [
    ("safe_py_sql.py", "JZ-SQLI-001"),
    ("safe_py_cmd.py", "JZ-CMDI-001"),
    ("safe_py_path.py", "JZ-TRAVERSAL-001"),
    ("safe_py_ssrf.py", "JZ-SSRF-001"),
    ("safe_py_deser.py", "JZ-DESER-001"),
    ("safe_py_eval.py", "JZ-CODE-001"),
    ("safe_py_redir.py", "JZ-REDIR-001"),
    ("safe_py_secret.py", "JZ-SECRET-001"),
    ("safe_py_authgap.py", "JZ-AUTHGAP-001"),
    ("safe_py_hash.py", "JZ-CRYPTO-001"),
    ("safe_js_sql.js", "JZ-SQLI-002"),
    ("safe_js_cmd.js", "JZ-CMDI-001"),
    ("safe_js_xss.jsx", "JZ-XSS-001"),
    ("safe_java_sql.java", "JZ-SQLI-003"),
    ("safe_php_sql.php", "JZ-SQLI-003"),
    ("safe_php_cipher.php", "JZ-CRYPTO-003"),
    ("safe_js_token.js", "JZ-JSINSEC-001"),
]

FILLER = (
    "def handle_%d(payload):\n"
    "    total = 0\n"
    "    for key, value in payload.items():\n"
    "        total += len(str(value))\n"
    "    return {\"id\": %d, \"total\": total}\n")


def line_of(text, probe):
    for i, line in enumerate(text.splitlines(), 1):
        if probe in line:
            return i
    return 0


def main():
    ap = argparse.ArgumentParser(description=u"生成审计验收语料（将作）")
    ap.add_argument("--out", required=True, help=u"语料输出目录（建议放在技能仓库之外）")
    ap.add_argument("--fillers", type=int, default=0, help=u"追加 N 个良性文件，用于内存曲线")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    if not os.path.isdir(out):
        os.makedirs(out)
    written = {}
    for group in (VULN, SAFE, DEPS):
        for rel, text in group.items():
            path = os.path.join(out, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            written[rel] = text
    for i in range(args.fillers):
        rel = "pkg/mod_%04d.py" % i
        text = FILLER % (i, i)
        fpath = os.path.join(out, rel.replace("/", os.sep))
        if not os.path.isdir(os.path.dirname(fpath)):
            os.makedirs(os.path.dirname(fpath))
        with io.open(fpath, "w",
                     encoding="utf-8", newline="\n") as f:
            f.write(text)
        written[rel] = text

    expected = {"find": [], "nofind": []}
    for rel, rule, probe in MUST_FIND:
        expected["find"].append({"file": rel, "rule_id": rule, "line": line_of(
            written.get(rel, ""), probe), "probe": probe})
    for rel, rule in MUST_NOT_FIND:
        expected["nofind"].append({"file": rel, "rule_id": rule})
    with io.open(os.path.join(out, "expected.json"), "w", encoding="utf-8",
                 newline="\n") as f:
        f.write(json.dumps(expected, ensure_ascii=False, indent=1) + "\n")
    print(u"语料已写出：%s（%d 个文件；应检出 %d 项、不应误报 %d 项）"
          % (out, len(written), len(MUST_FIND), len(MUST_NOT_FIND)))
    missing = [e for e in expected["find"] if e["line"] == 0]
    if missing:
        print(u"警告：以下 probe 在语料里定位不到行号，答案清单不可信：%s"
              % ", ".join("%s/%s" % (m["file"], m["rule_id"]) for m in missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
