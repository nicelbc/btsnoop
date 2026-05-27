# 回归测试方案

## 1. 概述

本文档定义每次代码变更后的回归验证策略，确保已有功能不被破坏。核心原则：**每次改动跑通全量测试 + 关键路径对比验证**。

## 2. 回归测试层次

```
┌─────────────────────────────────────────────┐
│ Level 3: Wireshark 对比验证 (发版前)         │  最慢，最权威
├─────────────────────────────────────────────┤
│ Level 2: 集成回归 (每次 PR)                  │  API + 端到端
├─────────────────────────────────────────────┤
│ Level 1: 单元回归 (每次 commit)              │  最快，最频繁
└─────────────────────────────────────────────┘
```

## 3. Level 1 — 单元回归 (每次 commit)

### 3.1 触发时机

- 开发者本地 commit 前 (pre-commit hook)
- CI 流水线 PR 创建/更新时

### 3.2 内容

```bash
cargo test --all          # 后端全量单元测试
cd frontend && pnpm test  # 前端全量组件测试
```

### 3.3 通过标准

- 0 个测试失败
- 执行时间 < 60s
- 任何失败阻塞 commit/merge

### 3.4 失败处理

```
测试失败 → 修复代码 → 重新提交
         ↗ 不允许：跳过测试、禁用用例、--no-verify
```

## 4. Level 2 — 集成回归 (每次 PR)

### 4.1 触发时机

- PR 创建/更新
- CI 自动执行

### 4.2 回归用例集

#### 4.2.1 文件解析回归

使用固定测试文件集验证解析正确性：

| 文件                      | 验证点                              |
|---------------------------|-------------------------------------|
| `testdata/sample.btsnoop` | 包总数、首包/末包时间戳、协议分布   |
| `testdata/ble_gatt.btsnoop` | ATT 操作码分布、GATT 服务发现结果 |
| `testdata/a2dp_streaming.btsnoop` | AVDTP 信令序列、Codec 配置参数 |
| `testdata/pairing_flow.btsnoop` | SMP 配对步骤、密钥类型         |
| `testdata/truncated.btsnoop` | 容错处理、部分解码成功           |
| `testdata/multi_conn.btsnoop` | 多连接 CID 映射隔离             |

#### 4.2.2 解码正确性回归

对比已保存的 "golden output"（预期结果快照）：

```bash
# 生成 golden output (首次或更新预期时执行)
cargo run --bin decode-file -- testdata/sample.btsnoop --json > testdata/golden/sample.json

# 回归验证
cargo run --bin decode-file -- testdata/sample.btsnoop --json | diff - testdata/golden/sample.json
```

Golden output 包含：
- 每个包的摘要 (summary)
- 每个包的协议名
- 包总数和类型分布

#### 4.2.3 过滤引擎回归

预定义过滤表达式 + 预期匹配数量：

```json
// testdata/filter_regression.json
[
  {"file": "sample.btsnoop", "filter": "hci.type == command", "expected_count": 45},
  {"file": "sample.btsnoop", "filter": "hci.type == event", "expected_count": 52},
  {"file": "sample.btsnoop", "filter": "direction == sent", "expected_count": 80},
  {"file": "ble_gatt.btsnoop", "filter": "l2cap.cid == 0x0004", "expected_count": 320},
  {"file": "ble_gatt.btsnoop", "filter": "att.opcode == 0x1B", "expected_count": 150},
  {"file": "a2dp_streaming.btsnoop", "filter": "l2cap.psm == 0x0019", "expected_count": 28}
]
```

#### 4.2.4 API 回归

```bash
# 启动测试服务器，执行全量 API 测试
cargo test --test api_integration
```

覆盖场景：
- 创建会话 → 上传文件 → 查询包列表 → 查询详情 → 关闭会话
- 非法文件上传 → 400
- 无效过滤 → 400
- 过期会话 → 404
- 并发上传同一会话 → 正确处理

### 4.3 通过标准

- 所有集成测试通过
- Golden output 差异为 0（或明确的预期变更）
- 过滤回归用例计数完全匹配

### 4.4 Golden Output 更新流程

当解码逻辑变更导致 golden output 差异时：

```
1. 确认差异是预期的（改进了解码精度）
2. 与 Wireshark 对比验证新结果正确
3. 更新 golden output 文件
4. 在 PR 描述中说明为什么 golden output 变了
5. Reviewer 需确认变更合理
```

## 5. Level 3 — Wireshark 对比验证 (发版前)

### 5.1 触发时机

- 版本发布前
- 解码器核心逻辑变更后
- 新协议支持完成后

### 5.2 对比方法

```bash
# 1. 使用 tshark 生成参考解码
tshark -r testdata/sample.btsnoop -T json \
  -e frame.number -e frame.time_relative \
  -e bthci_cmd.opcode -e bthci_evt.code \
  -e btl2cap.cid -e btl2cap.psm \
  -e btatt.opcode -e btatt.handle \
  > reference/sample_wireshark.json

# 2. 生成我们的解码结果
cargo run --bin decode-file -- testdata/sample.btsnoop --compare-format \
  > reference/sample_ours.json

# 3. 运行对比脚本
python3 scripts/compare_with_wireshark.py \
  reference/sample_wireshark.json \
  reference/sample_ours.json \
  --report reference/comparison_report.md
```

### 5.3 对比字段

| 协议层 | 对比字段                                    |
|--------|---------------------------------------------|
| HCI    | opcode, event_code, handle, status          |
| L2CAP  | cid, psm, length, signaling_code           |
| ATT    | opcode, handle, error_code                  |
| SMP    | code, io_capability, reason                 |
| AVDTP  | signal_id, message_type, seid              |

### 5.4 差异分类

| 差异类型        | 处理方式                          |
|-----------------|-----------------------------------|
| 值不一致        | Bug — 必须修复后才能发版          |
| 我们多了字段    | 可接受 — 我们提供了更多信息       |
| 我们少了字段    | 评估 — P2 以上优先级需补充        |
| 格式不同        | 可接受 — 只要语义一致             |
| Vendor 命令差异 | 可接受 — Wireshark 可能不支持     |

### 5.5 通过标准

- 关键字段（opcode, event_code, handle, cid, psm）一致率 ≥ 99%
- 无值错误（允许格式差异）
- 不支持的协议/字段需记录到已知限制列表

## 6. 回归测试文件管理

### 6.1 测试文件集

```
testdata/
├── regression/
│   ├── basic_hci.btsnoop           # HCI 命令/事件基础
│   ├── acl_l2cap.btsnoop           # L2CAP 信令 + 数据
│   ├── ble_gatt_discovery.btsnoop  # BLE 服务发现完整流程
│   ├── ble_gatt_rw.btsnoop         # GATT 读写通知
│   ├── a2dp_sbc.btsnoop            # SBC 编码 A2DP 流
│   ├── a2dp_aac.btsnoop            # AAC 编码 A2DP 流
│   ├── a2dp_ldac.btsnoop           # LDAC A2DP 流
│   ├── a2dp_lhdc.btsnoop           # LHDC A2DP 流
│   ├── a2dp_aptx.btsnoop           # aptX A2DP 流
│   ├── smp_legacy_pairing.btsnoop  # Legacy 配对
│   ├── smp_secure_conn.btsnoop     # Secure Connections 配对
│   ├── multi_connection.btsnoop    # 多连接并存
│   ├── reconnection.btsnoop        # 断连重连
│   └── edge_cases/
│       ├── empty.btsnoop           # 只有文件头
│       ├── truncated_mid.btsnoop   # 中间截断
│       ├── huge_packet.btsnoop     # 超大包
│       ├── zero_length.btsnoop     # 零长包
│       └── bad_timestamp.btsnoop   # 异常时间戳
├── golden/
│   ├── basic_hci.json              # 预期解码结果
│   ├── acl_l2cap.json
│   ├── ...
│   └── filter_counts.json          # 过滤预期计数
└── wireshark_reference/
    ├── basic_hci_tshark.json       # tshark 导出参考
    └── ...
```

### 6.2 测试文件来源

| 来源                     | 用途                    |
|--------------------------|-------------------------|
| 真实设备抓包             | 主要来源，覆盖真实场景  |
| 手工构造                 | 边界用例和异常用例      |
| bt-snoop-live 验证过的   | 基线正确性保证          |
| Android CTS 抓包         | 标准协议流程            |

### 6.3 新增测试文件规则

添加新回归文件时必须：
1. 先用 bt-snoop-live 或 Wireshark 确认文件可正常解析
2. 生成对应的 golden output
3. 添加到 `filter_regression.json` 中
4. 在 PR 中说明文件的用途和覆盖场景

## 7. 自动化执行

### 7.1 本地执行

```bash
# 快速回归 (Level 1，<30s)
make test

# 完整回归 (Level 1 + Level 2，<3min)
make regression

# 对比验证 (Level 3，需要安装 tshark)
make compare-wireshark
```

### 7.2 CI 集成

```yaml
# PR 级别: Level 1 + Level 2
regression:
  steps:
    - cargo test --all
    - cargo run --bin regression-check
    - cd frontend && pnpm test

# 发版级别: 全部
release-validation:
  steps:
    - cargo test --all
    - cargo run --bin regression-check
    - cargo run --bin wireshark-compare
    - cargo bench -- --save-baseline release
```

## 8. 回归失败响应流程

```
回归失败
  │
  ├─ 单元测试失败 → 修复代码，重新提交
  │
  ├─ Golden output 差异
  │   ├─ 预期差异 → 更新 golden + PR 说明
  │   └─ 非预期差异 → 修复 Bug
  │
  ├─ 过滤计数不匹配
  │   ├─ 解码变更导致 → 更新预期计数 + 确认正确性
  │   └─ 过滤 Bug → 修复
  │
  └─ Wireshark 对比失败 → 阻塞发版，修复后重新验证
```

## 9. 已知限制

维护一份已知差异列表（与 Wireshark 对比时的合理差异）：

```markdown
# known_differences.md

## 合理差异

1. Vendor Specific HCI 命令：我们支持 MTK 扩展命令解码，Wireshark 可能显示为 Unknown
2. LHDC Codec 参数：我们使用最新 LHDC V5 规格解码，Wireshark 版本可能未更新
3. 时间戳精度：我们保留微秒，Wireshark 显示毫秒（对比时需容差）
4. BD_ADDR 格式：我们用大写 "AA:BB:CC"，Wireshark 可能小写 — 对比时 normalize
```
