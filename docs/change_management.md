# 变更管理与质量门禁文档

## 1. 概述

本文档定义代码变更流程、质量门禁规则和发布流程。所有代码变更必须通过规定的检查后才可合入主分支。

## 2. 变更流程

### 2.1 开发流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Create  │───→│  Develop │───→│  Local   │───→│  Submit  │───→│  Review  │
│  Branch  │    │  & Test  │    │  Verify  │    │  PR      │    │  & Merge │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### 2.2 分支策略

```
main ─────────────────────────────────────────────────
  │                        ↑              ↑
  ├── feature/xxx ────────PR──────────────┘
  │                        
  ├── fix/xxx ────────────PR──────────────────────────┘
  │
  └── release/v1.x (发版时创建)
```

- `main`: 主分支，始终保持可发布状态
- `feature/*`: 功能分支，从 main 创建
- `fix/*`: 修复分支，从 main 创建
- `release/*`: 发布分支，仅用于 hotfix

### 2.3 Commit 规范

每次 commit 必须：
- 通过本地预检查 (`pre-commit hook`)
- 遵循 Conventional Commits 格式
- 单一职责（一个 commit 做一件事）

```
feat(decoder): add SDP protocol decoding
fix(parser): handle zero-length packet record
test(filter): add boundary test cases for nested expressions
refactor(frontend): extract protocol tree into reusable component
docs(api): update WebSocket message format
chore(ci): add performance regression check
```

## 3. 本地预检查 (Pre-commit)

### 3.1 必须通过的检查

开发者在提交前必须在本地运行以下检查：

```bash
# 一键运行所有本地检查
make check

# 等价于以下步骤：
cargo fmt --check                    # 格式检查
cargo clippy -- -D warnings          # 静态分析
cargo test                           # 全量单元测试 + 集成测试
cd frontend && pnpm lint             # ESLint
cd frontend && pnpm type-check       # TypeScript 类型检查
cd frontend && pnpm test             # 前端测试
```

### 3.2 Git Hook 配置

```bash
# .githooks/pre-commit
#!/bin/bash
set -e

echo "=== Running pre-commit checks ==="

echo "[1/6] cargo fmt..."
cargo fmt --check

echo "[2/6] cargo clippy..."
cargo clippy -- -D warnings

echo "[3/6] cargo test..."
cargo test

echo "[4/6] frontend lint..."
cd frontend && pnpm lint

echo "[5/6] frontend type-check..."
cd frontend && pnpm type-check

echo "[6/6] frontend test..."
cd frontend && pnpm test

echo "=== All checks passed ==="
```

### 3.3 跳过规则

**严格禁止跳过 pre-commit hook**（`--no-verify`）。如果测试失败，必须修复后再提交。

唯一例外：纯文档修改（仅 `.md` 文件）可跳过测试步骤（但仍需格式检查）。

## 4. CI 门禁 (PR 级别)

### 4.1 必须通过的 CI 检查

PR 合入 main 前，以下所有检查必须通过：

| 检查项                    | 超时   | 失败处理           |
|--------------------------|--------|-------------------|
| cargo fmt --check        | 1 min  | 阻塞合入           |
| cargo clippy -D warnings | 3 min  | 阻塞合入           |
| cargo test               | 5 min  | 阻塞合入           |
| cargo bench (回归检测)   | 10 min | 回归 >50% 阻塞    |
| pnpm lint                | 2 min  | 阻塞合入           |
| pnpm type-check          | 2 min  | 阻塞合入           |
| pnpm test                | 3 min  | 阻塞合入           |
| pnpm build               | 3 min  | 阻塞合入           |
| 覆盖率检查               | 5 min  | 低于阈值时告警     |
| 安全扫描 (cargo audit)   | 2 min  | Critical 漏洞阻塞  |

### 4.2 CI Pipeline 定义

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: rustfmt, clippy

      - name: Format check
        run: cargo fmt --check

      - name: Clippy
        run: cargo clippy -- -D warnings

      - name: Test
        run: cargo test --all

      - name: Benchmark regression check
        run: |
          cargo bench -- --output-format bencher | tee bench_results.txt
          # 与 main 分支基线对比，回归 >50% 则失败

      - name: Security audit
        run: cargo audit

      - name: Coverage
        run: cargo tarpaulin --out xml
        # 上传覆盖率报告

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v2
      - uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'pnpm'

      - run: cd frontend && pnpm install --frozen-lockfile
      - run: cd frontend && pnpm lint
      - run: cd frontend && pnpm type-check
      - run: cd frontend && pnpm test
      - run: cd frontend && pnpm build
```

### 4.3 性能回归检测

每次 PR 运行 benchmark，与 main 分支最近基线对比：

```
指标回归处理规则：
  回归 < 20%  → PASS（允许合入）
  回归 20-50% → WARNING（需在 PR 中说明原因）
  回归 > 50%  → FAIL（阻塞合入，必须优化或说明必要性）
```

## 5. Code Review 规则

### 5.1 审查要求

- 所有 PR 至少需要 1 人 Approve
- 涉及解码器核心逻辑的变更需要 2 人 Approve
- 涉及安全相关（输入验证、资源限制）的变更需要安全 owner Approve

### 5.2 审查关注点

| 维度       | 检查项                                           |
|-----------|--------------------------------------------------|
| 正确性    | 解码逻辑是否与蓝牙规格一致                        |
| 安全性    | 边界检查是否完备、是否有 panic 路径              |
| 性能      | 热路径是否有不必要的分配、是否有 O(n²) 循环      |
| 测试      | 新增代码是否有对应测试、边界用例是否覆盖         |
| API 兼容  | 是否有 breaking change、是否需要版本升级         |

### 5.3 PR 描述模板

```markdown
## 变更说明

<!-- 用 1-3 句话描述做了什么 -->

## 变更类型

- [ ] 新功能 (feat)
- [ ] Bug 修复 (fix)
- [ ] 重构 (refactor)
- [ ] 测试 (test)
- [ ] 文档 (docs)

## 测试情况

- [ ] 新增单元测试 _____ 个
- [ ] 全部测试通过
- [ ] 性能 benchmark 无回归

## 影响范围

<!-- 列出受影响的模块 -->

## 对比验证 (解码器变更时必填)

<!-- 与 Wireshark 解码结果对比截图或说明 -->
```

## 6. 质量门禁总结

### 6.1 变更级别门禁

```
代码变更 → 本地 pre-commit → 推送 → CI 检查 → Review → Merge
                │                     │          │
                ▼                     ▼          ▼
           格式 + Lint           全量测试    人工审查
           + 全量测试           + Benchmark   正确性/安全性
                                + 覆盖率
                                + 安全扫描
```

### 6.2 不可绕过的硬性规则

以下规则**任何情况下不可绕过**：

1. **测试必须通过** — 任何测试失败都不允许合入
2. **禁止 `--no-verify`** — 不允许跳过 pre-commit hook
3. **禁止 force push main** — main 分支受保护
4. **新增代码必须有测试** — 无测试的功能代码不允许合入
5. **解码器变更必须有对比验证** — 与 Wireshark 解码结果一致

### 6.3 可申请豁免的软性规则

以下情况可在 PR 中说明理由后豁免：

- 覆盖率不达标（但不可低于 60%）
- 性能回归 20-50%（需说明必要性）
- 未添加新测试（纯重构且现有测试覆盖）

## 7. 发布流程

### 7.1 版本号规范

遵循 Semantic Versioning：

```
MAJOR.MINOR.PATCH

MAJOR: API 不兼容变更
MINOR: 新增功能（向后兼容）
PATCH: Bug 修复
```

### 7.2 发布 Checklist

- [ ] main 分支所有 CI 通过
- [ ] 全量 E2E 测试通过
- [ ] 性能 benchmark 与上一版本对比无明显回归
- [ ] CHANGELOG.md 更新
- [ ] Docker 镜像构建成功
- [ ] 在 staging 环境验证通过
- [ ] 安全扫描通过

### 7.3 Hotfix 流程

```
main ──────────────────────────────────────
  │
  ├── release/v1.0 ─── hotfix commit ──→ tag v1.0.1
  │                         │
  │                    cherry-pick to main
  ▼
```

Hotfix 同样必须通过全部 CI 检查，不可绕过。

## 8. 回滚策略

### 8.1 回滚触发条件

- 线上发现 Critical bug（数据解析错误、崩溃）
- 性能严重回归（响应时间 > 2x 基线）
- 安全漏洞

### 8.2 回滚操作

```bash
# 回滚到上一个 release tag
git revert <commit-hash>  # 创建 revert commit
# 走正常 CI/Review 流程（加急）

# 紧急情况（需 2 人确认）
docker tag btsnoop-web:v1.0.0 btsnoop-web:latest
docker compose up -d
```

### 8.3 回滚后复盘

回滚后 24 小时内必须完成 postmortem：
- 根因分析
- 为什么测试没有捕获
- 补充测试用例
- 流程改进措施
