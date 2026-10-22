# 结论区逐条判定表（将作 · 将作 jiangzuo）

> **这份表回答一个具体问题**：审计链报的每一条，到底是真漏洞还是误报？
> E20 逐条判过一次（`v0.54.0` 节），但那次的判定**有三处偏差**（见下），
> 且把一条**在另计档（测试语境）**的条目算进了分子。
> **E28（v0.62.0）把结论区 62 条全部重判一遍**（DVWA 61 + flask 1 + requests 0），
> 判定依据是**每条的完整证据链 + 必要时读源码**（不是只看 sink 行）。
> **E29（v0.63.0）修掉最后一条「静态可修」的误报**（纯常量 `document.write`）
> ⇒ 结论区 **61 条**、误报 **6 条**，**「静态可修」这一类归零 ⇒ 硬误报清零**。
>
> **口径声明**：分母＝**结论区条数**（＝正式代码语境里的发现；测试/示例语境另计，不进分母）。
> 分子＝**已判定为"检测错了"的条数**。**未判定 = 0**（E20 留下的 3 条已全部有结论）。
>
> **复现命令**（结论区条数会随规则/引擎变化 ⇒ 先取数再对表）：
> ```bash
> python scripts/audit_scan.py <第三方仓库> --json ../eval-runs/scan.json
> python -c "import json;d=json.load(open('../eval-runs/scan.json'));print(d['stats']['conclusions'])"
> ```

## 一、汇总（按规则）

| 规则 | 结论区条数 | 真阳性 | 误报 | 备注 |
|---|---|---|---|---|
| JZ-CMDI-001 | 7 | 7 | 0 | DVWA exec 模块 + `api/src/HealthController.php:88`（`php://input` → `exec`） |
| JZ-CODE-001 | 2 | 2 | 0 | `view_help.php:20,22`：`$_GET['id']` → `eval('?>' . file_get_contents(...))`（LFI→RCE） |
| JZ-SQLI-003 | 14 | 12 | 2 | 误报见 §二 #1、#2 |
| JZ-SECRET-001 | 1 | 0 | 1 | 误报见 §二 #3 |
| JZ-XSS-002 | 2 | 2 | 0 | `csp/source/jsonp.php:12`（JSONP 回调未校验）、`xss_r/source/low.php:8`（反射 XSS） |
| JZ-TRAVERSAL-001 | 1 | 1 | 0 | `fi/index.php:36`：`include($file)`，源在被 include 的文件里 |
| JZ-CRYPTO-003 | 5 | 5 | 0 | `aes-128-ecb` ×3、逐字符异或 ×2 |
| JZ-XSS-001 | 11 | 9 | 2 | 误报见 §二 #4、#5（#6 已由 E29 修掉，不再计入） |
| JZ-JSINSEC-001 | 2 | 2 | 0 | `javascript/source/high_unobfuscated.js:523,527`（客户端算令牌） |
| JZ-UPLOAD-001 | 1 | 1 | 0 | `upload/source/low.php:9`：`move_uploaded_file($_FILES[...]['tmp_name'], $target_path)` |
| JZ-REDIR-001 | 3 | 3 | 0 | `open_redirect/source/{low,medium,high}.php` |
| JZ-WEAKID-001 | 5 | 5 | 0 | `md5(uniqid())`、`$_SESSION['last_session_id']++`、`time()` |
| JZ-CSRF-001 | 6 | 6 | 0 | 六个 `<form method=post>` 无 token |
| **DVWA 小计** | **60** | **55** | **5** | |
| flask（`src/flask/json/tag.py:188`） | 1 | 0 | 1 | 误报见 §二 #7 |
| requests | 0 | 0 | 0 | 4 条全在 `library_feature` / `test` 语境 ⇒ 另计，不进分母 |
| **合计** | **61** | **55** | **6** | |

## 二、误报逐条（在册 6 条 + 已修 1 条留档；为什么是误报、归哪一类、怎么处置）

| # | 位置 | 形态 | 为什么是误报 | 归类 | 处置 |
|---|---|---|---|---|---|
| 1 | `vulnerabilities/bac/index.php:58` | 把一个**被 include 的文件**里用 `intval` 处理过的 id 拼进查询 | `intval` 确实把 `$id` 变成整数 ⇒ SQL 注入不成立；但**净化点在另一个文件**，引擎的 guard 只扫**同文件**的函数体 ⇒ 没拦住 | **待能力升级**（净化点跨文件作用域） | E31 一起做（净化点的作用范围跨到被 include 的文件） |
| 2 | `vulnerabilities/csrf/source/high.php:44` | 更新语句里拼的口令字段，第 38 行先过了 `mysqli_real_escape_string` | 转义在**引号内**有效 ⇒ 不是注入；但引擎不知道这个 sink 的 SQL 上下文 | **待能力升级**（净化点按 sink 上下文） | E30 |
| 3 | `vulnerabilities/sqli/test.php:4` | 口令字段被赋成一个**带四个星号**的字符串 | 那是**占位/脱敏值**，不是真凭据（⚠️ 原文里那一行长得像赋值真口令 ⇒ 本文档**不复制**它，免得被密钥扫描当泄露） | **静态消不掉** | 属**能力边界**：要认出"占位值"必须看**字符串内容**，而规则跑在**掩码桶**（字面量被剥）上 ⇒ 登记为边界 |
| 4 | `vulnerabilities/csp/source/high.js:9` | 把 JSONP 响应里的 answer 字段写进 innerHTML | `obj` 来自 `source/jsonp.php`，而那个 php 里 `$outp = array("answer" => "15")` 是**常量** ⇒ 插进 DOM 的永远是 `"15"` | **静态消不掉** | 属**能力边界**：要判"服务端返回什么"得读服务端代码 ⇒ 边界 |
| 5 | `vulnerabilities/csp/source/impossible.js:9` | 同上（修复档） | `source/jsonp_impossible.php` 里 `$outp` 同样是常量 ⇒ 修复档里同样插常量 | **静态消不掉** | 同上 |
| 6 | `vulnerabilities/xss_d/index.php:54` | 用 `document.write` 写一段**纯常量** HTML | 纯**字符串常量** ⇒ 不是 XSS（上一行 `:53` 才是带变量的那行） | **已修**（静态可修，E29 清零） | ✅ **E29 已修**：`document.write` 分支加**负向先行**（掩码形态 `document.write('');` ⇒ 负向要容忍 `''` 与 `;` 之间的 `)`）⇒ 这条误报消失，且**真阳性一条没丢**（A/B 逐条：DVWA 只少这一条、新增 0 条） |
| 7 | flask `src/flask/json/tag.py:188` | JSON 反序列化标签里把**已反序列化的对象**包回 Markup | 这是 `TagMarkup.to_python()`：JSON 反序列化时把**已反序列化的对象**包回 Markup（`check()` 要求对象已有 `__html__`）⇒ 不是"把不可信数据当 HTML" | **静态消不掉** | 属**能力边界**：`Markup(user_input)`（真阳性）与 `Markup(value)`（本条）**形态完全相同** ⇒ 静态不可区分 |

## 三、三类误报的口径（E28 建立，E29 把「静态可修」清零）

| 类别 | 条数 | 含义 | 能不能靠改规则消掉 |
|---|---|---|---|
| **静态可修** | 0 | E29 已把最后一条修掉 ⇒ 这一类**归零** | — |
| **待能力升级** | 2 | 净化点的作用范围/上下文，引擎目前看不到 | 不能（要改引擎 ⇒ E30 / E31） |
| **静态消不掉（能力边界型）** | 4 | 形态与真阳性**完全相同**，静态无从区分 | **不能**（属"能力边界"，已写进 `references/audit-rule-authoring.md` 的边界表） |

⇒ **所以"硬误报"这个笼统的分子应当拆开**：
E20 说"硬误报 8 条"，其中 5 条是规则过宽（E25/E26 已修）、
1 条**根本不在结论区**（`csrf/test_credentials.php:22` 在**测试语境**⇒ 另计），
**真正在结论区且当时判错的只有 2 条**；E28 逐条重判后又挖出 **E20 没抓到的 4 条**（#1、#3、#4、#7）。

⇒ **现行口径**：
- 结论区 **61** 条＝真阳性 **55** + 误报 **6**
- 误报 6 条＝静态可修 **0** + 待能力升级 **2** + 静态消不掉 **4**
- ⇒ **"静态可修的硬误报"= 0 / 61 = 0%**（E20 的 8/69 ≈ 11.6% ⇒ 降了 100%）
- ⇒ **未判定 = 0**（E20 留下的一切皆有结论）

⚠️ **口径纪律**：分子分母必须同范围；每改一次规则/引擎，**这张表要重判**（判定表不是永久有效的）。
