# 分册：接手陌生项目（摸底）

> **何时读**：第一次接触一个代码库；接手别人的项目；L3 项目开始前；长时间没碰的项目回来时。
> **前置**：能访问项目目录。
> **产出**：`docs/jiangzuo/profiles/` 下的项目摸底档案（templates/project-profile.md）。

## 原则

摸底的目的是建立"地图"，不是读完全部代码。目标是能回答：**这是什么、怎么跑起来、怎么验证、改动会牵动哪里**。禁止跳过摸底直接改代码。

**遗留系统**（无测试、无文档、没人懂）：先建立"冒烟验证"——改动前先弄清怎么确认核心功能没被弄坏（哪怕就是手动点一遍主流程），再谈修改。

## 可执行步骤

1. **自动扫描**：`python <技能目录>/scripts/project_scan.py . --out docs/jiangzuo/profiles/project-profile.md`，得到档案草稿。没有 Python 就按下面步骤手动做。
2. **识别技术栈**：读根目录的清单文件——`package.json` / `pyproject.toml` / `requirements.txt` / `go.mod` / `pom.xml` / `build.gradle` / `Cargo.toml` / `composer.json` / `*.csproj` / `Gemfile`。记录：语言、框架及版本、关键依赖（ORM、状态管理、UI 库）。
3. **目录结构**：看根目录和 `src/`（或同级主代码目录）一到两层，给每个顶层目录写一句话职责。看出分层模式（如 controller/service/model、pages/components/api）。monorepo 则分别识别每个包/应用（`apps/*`、`packages/*`）的栈与命令。
4. **启动与构建方式**：按顺序找——README 的 Quick Start → package.json 的 scripts / Makefile / pyproject scripts → `.github/workflows/` 或其他 CI 配置。找到就把命令记进档案（如 `npm run dev`、`uvicorn app.main:app --reload`）。
5. **测试方式**：找测试目录（`tests/`、`__tests__/`、`*.test.*`、`*_test.go`）和测试命令（`npm test`、`pytest`、`go test ./...`）。**运行一次测试确认能跑通**，记录基线结果。跑不起来也如实记录原因——这本身就是重要发现。
6. **配置与环境**：找 `.env.example` / `config/` / `docker-compose.yml`。列出运行需要哪些环境变量、外部服务（数据库、缓存、第三方 API）。
7. **关键调用链**：挑一个核心流程（如"用户提交订单"）从入口开始追：路由 → 控制器 → 服务 → 数据层。目的不是背下来，而是知道"改 X 会经过哪些层"。
8. **项目惯例**：看 2-3 个现有同类文件（如已有的一组接口、一个组件），记下命名风格、错误处理方式、注释密度、测试写法。**你的新代码要长得像这个项目的代码。**
9. **近期动态**：`git log --oneline -20` 看最近在做什么；有 `CHANGELOG`、`docs/` 就扫一眼。
10. **落盘**：把以上内容填进 templates/project-profile.md，存到 `docs/jiangzuo/profiles/`。向用户用三五句话汇报项目认知，请他纠偏。

**跑不起来怎么办**（这本身就是摸底的一部分，不要跳过）：
1. 读完整报错，判断缺什么：依赖、环境变量、数据库、端口、版本。
2. 对照 `.env.example` 和 README 快速启动段逐项核对。
3. 依赖版本对不上 → 按锁文件重装；数据库连不上 → 先确认服务在跑、连接串对不对。
4. 30 分钟仍起不来：把已尝试步骤和报错汇总后问用户/团队，不无限死磕。
5. 无论结果如何，把卡点落进摸底档案——"项目当前起不来"是重要事实。

## 摸底完成的标准（能全部回答）

- [ ] 技术栈和关键版本说得出来
- [ ] 给出启动项目的确切命令（并实际跑通过，或说明了跑不通的原因）
- [ ] 给出运行测试的确切命令（并实际跑过一次）
- [ ] 说出代码分层和至少一条关键调用链
- [ ] 列出必需的环境变量和外部依赖
- [ ] 说出项目代码风格的 2-3 个特点
- [ ] 摸底档案已落盘

## 示例

**好的摸底汇报**：
> 这是一个 React 18 + Vite 前端、FastAPI 后端的项目。前端 `npm run dev` 启动，后端 `uvicorn app.main:app --reload`；测试用 pytest（当前 42 个全绿）和 vitest（3 个跳过，原因待查）。分层是 router → service → repository，数据库用 SQLAlchemy + Alembic 迁移。用户下单流程：`app/api/orders.py:submit_order` → `services/order.py:create` → `repositories/order_repo.py:insert`。需要本地 Postgres，连接串在 `.env`（参考 `.env.example`）。摸底档案已存 `docs/jiangzuo/profiles/project-profile.md`，有两点没看懂想跟你确认：……

**失败的摸底**：
> "好的，我来加这个功能。"（没跑过项目、不知道测试命令、没看现有代码风格，直接开写。）

## 常见错误

- 没让项目跑起来、没跑过一次测试，就宣称"了解项目了"。
- 忽略 `.env.example`，写完代码才发现缺环境变量。
- 拿通用框架知识当项目事实（"Express 项目肯定是这样组织的"）——一切以实际读到的为准。
- 档案写完就丢，L2/L3 后续阶段不再回来更新。
