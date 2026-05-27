# Btsnoop 在线实时解析工具 - 技术设计文档

## 1. 项目概述

### 1.1 背景

btsnoop 是蓝牙 HCI (Host Controller Interface) 层的抓包文件格式，广泛用于 Android 蓝牙调试。当前调试流程通常为：导出 btsnoop 文件 → 用 Wireshark 离线分析。该流程存在以下痛点：

- 需要本地安装 Wireshark 等工具
- 无法实时查看正在进行的蓝牙交互
- 团队协作时需要传递文件
- 移动端调试场景下操作繁琐

### 1.2 目标

构建一个基于 Web 的 btsnoop 实时解析工具，支持：

- 浏览器内拖拽上传或实时流式解析
- HCI/L2CAP/上层协议的逐层解码
- 实时过滤、搜索、高亮
- 多人共享同一抓包会话

## 2. Btsnoop 文件格式

### 2.1 文件头 (File Header)

```
Offset  Size  Description
0       8     Identification Pattern: "btsnoop\0"
8       4     Version Number (uint32, big-endian), 当前为 1
12      4     Datalink Type (uint32, big-endian)
```

Datalink Type 取值：

| 值    | 含义                              |
|-------|-----------------------------------|
| 1001  | Un-encapsulated HCI (H1)         |
| 1002  | HCI UART (H4)                    |
| 1003  | HCI BSCP                         |
| 1004  | HCI Serial (H5)                  |
| 2001  | Monitor (Linux Bluetooth Monitor) |

### 2.2 数据包记录 (Packet Record)

每条记录格式：

```
Offset  Size  Description
0       4     Original Length (uint32, big-endian)
4       4     Included Length (uint32, big-endian)
8       4     Packet Flags (uint32, big-endian)
12      4     Cumulative Drops (uint32, big-endian)
16      8     Timestamp Microseconds (int64, big-endian, 自 2000-01-01 起)
24      N     Packet Data (N = Included Length)
```

Packet Flags 含义：

| Bit 0 | 方向        | Bit 1 | 类型           |
|-------|-------------|-------|----------------|
| 0     | Sent (Host→Controller) | 0 | Data (ACL/SCO) |
| 1     | Received (Controller→Host) | 1 | Command/Event  |

### 2.3 时间戳转换

```
btsnoop_epoch = 2000-01-01 00:00:00 UTC
unix_timestamp_us = btsnoop_timestamp - 0x00dcddb30f2f8000
```

## 3. 系统架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (Browser)                   │
├──────────┬──────────┬───────────────┬───────────────────┤
│ File     │ Packet   │ Detail View   │ Hex Dump          │
│ Upload   │ List     │ (Protocol     │ View              │
│ / Stream │ View     │  Decode Tree) │                   │
└────┬─────┴────┬─────┴───────┬───────┴───────────────────┘
     │          │             │
     │ WebSocket / HTTP       │
     │          │             │
┌────▼──────────▼─────────────▼───────────────────────────┐
│                    Backend Server                         │
├──────────┬──────────┬───────────────┬───────────────────┤
│ Stream   │ Protocol │ Session       │ Filter            │
│ Parser   │ Decoder  │ Manager       │ Engine            │
└──────────┴──────────┴───────────────┴───────────────────┘
```

### 3.2 技术栈选型

| 层级     | 技术方案                          | 选型理由                        |
|----------|-----------------------------------|---------------------------------|
| Frontend | React + TypeScript + Virtualized List | 大数据量渲染，类型安全         |
| 通信     | WebSocket + Binary Protocol       | 低延迟，支持流式传输           |
| Backend  | Rust (Axum) 或 Go (Gin)          | 高性能二进制解析               |
| 存储     | 内存 + 可选 SQLite                | 会话级临时存储，无需持久化     |

### 3.3 模块划分

```
btsnoop-web/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── PacketList.tsx       # 虚拟列表，展示数据包摘要
│   │   │   ├── ProtocolTree.tsx     # 协议解码树
│   │   │   ├── HexView.tsx          # 十六进制/ASCII 查看器
│   │   │   ├── FilterBar.tsx        # 过滤表达式输入
│   │   │   └── UploadZone.tsx       # 文件拖拽上传区
│   │   ├── parser/
│   │   │   └── btsnoop-wasm.ts      # WASM 解析器绑定 (可选前端解析)
│   │   ├── stores/
│   │   │   └── packetStore.ts       # 全局状态管理
│   │   └── ws/
│   │       └── client.ts            # WebSocket 客户端
│   └── package.json
├── backend/
│   ├── src/
│   │   ├── parser/
│   │   │   ├── btsnoop.rs           # btsnoop 文件头/记录解析
│   │   │   ├── hci.rs               # HCI 层解码
│   │   │   ├── l2cap.rs             # L2CAP 层解码
│   │   │   ├── sdp.rs               # SDP 协议解码
│   │   │   ├── rfcomm.rs            # RFCOMM 协议解码
│   │   │   ├── avdtp.rs             # AVDTP/A2DP 解码
│   │   │   ├── avctp.rs             # AVCTP/AVRCP 解码
│   │   │   ├── att.rs               # ATT/GATT 解码 (BLE)
│   │   │   ├── smp.rs               # SMP 配对协议解码
│   │   │   └── iso.rs               # ISO (LE Audio) 解码
│   │   ├── filter/
│   │   │   ├── engine.rs            # 过滤表达式引擎
│   │   │   └── grammar.rs           # 过滤语法定义
│   │   ├── session/
│   │   │   └── manager.rs           # 会话生命周期管理
│   │   └── ws/
│   │       └── handler.rs           # WebSocket 处理
│   └── Cargo.toml
└── README.md
```

## 4. 核心功能设计

### 4.1 流式解析引擎

支持两种输入模式：

**模式一：文件上传解析**

```
Browser ──[HTTP multipart upload]──→ Server
         ←─[WebSocket: parsed packets]─┘
```

文件分块读取，边解析边推送，前端逐步渲染。用户无需等待整个文件解析完毕。

**模式二：实时流推送**

```
Device/ADB ──[TCP/adb forward]──→ Server ──[WebSocket]──→ Browser
```

通过 `adb shell cat /dev/btsnoop_hci` 或 Android BT logging 接口获取实时数据流。

### 4.2 协议解码栈

解码顺序遵循蓝牙协议栈层次：

```
             ┌─────────────┐
             │  Application │ (OBEX, MAP, PBAP...)
             ├─────────────┤
             │  SDP / ATT  │
             ├─────────────┤
             │  RFCOMM     │   ┌──────┐
             ├─────────────┤   │ AVDTP│
             │   L2CAP     │   │ AVCTP│
             ├─────────────┴───┴──────┤
             │        HCI              │
             ├─────────────────────────┤
             │  HCI Transport (H4/H5) │
             └─────────────────────────┘
```

每层解码器输出结构化数据：

```typescript
interface DecodedLayer {
  protocol: string;          // e.g. "HCI", "L2CAP", "ATT"
  summary: string;           // 单行摘要
  fields: DecodedField[];    // 各字段解码结果
  payload_offset: number;    // 上层协议起始偏移
  payload_length: number;
}

interface DecodedField {
  name: string;
  value: string | number;
  offset: number;            // 字节偏移 (用于 HexView 高亮)
  length: number;
  children?: DecodedField[];
}
```

### 4.3 HCI 解码细节

HCI 包类型（H4 Transport）：

| Indicator | Type              |
|-----------|-------------------|
| 0x01      | HCI Command       |
| 0x02      | ACL Data          |
| 0x03      | SCO Data          |
| 0x04      | HCI Event         |
| 0x05      | ISO Data (BT 5.2) |

HCI Command 解码示例：

```
Byte:  [01] [03 04] [04] [00 01 02 03]
        │    │       │    └── Parameters
        │    │       └── Parameter Total Length
        │    └── OpCode (OGF=0x01, OCF=0x0003 → HCI_Connection_Request)
        └── HCI Command Indicator
```

### 4.4 过滤引擎

支持类 Wireshark 的显示过滤语法：

```
# 基础字段过滤
hci.type == command
hci.opcode == 0x0406
l2cap.cid == 0x0040
att.opcode == 0x12

# 方向过滤
direction == sent
direction == received

# 地址过滤
hci.handle == 0x0001
bt.addr == "AA:BB:CC:DD:EE:FF"

# 组合表达式
hci.type == acl && l2cap.psm == 0x0003
att.opcode == write_req || att.opcode == write_cmd

# 文本搜索
contains "GATT"
```

过滤语法使用 PEG 解析器实现，编译为过滤函数后对每个包执行匹配。

### 4.5 前端虚拟列表

百万级数据包的流畅渲染方案：

- 使用 `react-virtuoso` 或 `@tanstack/react-virtual` 做虚拟滚动
- 仅渲染可视区域 ± 缓冲区内的行
- 数据包摘要在后端预计算，前端不做重复解码
- 选中某行时才请求完整解码树

```typescript
// 包列表每行数据结构（轻量）
interface PacketSummary {
  index: number;
  timestamp: number;
  direction: "sent" | "received";
  type: string;           // "CMD" | "EVT" | "ACL" | "SCO" | "ISO"
  protocol: string;       // 最高层协议名
  summary: string;        // 单行描述
  length: number;
}
```

## 5. 通信协议设计

### 5.1 WebSocket 消息格式

采用二进制帧 + JSON 混合方案：

```
客户端 → 服务端 (JSON):
{
  "type": "upload_chunk" | "set_filter" | "get_detail" | "start_live",
  "payload": { ... }
}

服务端 → 客户端 (Binary Frame):
┌───────┬──────────┬─────────────────────┐
│ MsgType│ Length   │ Payload             │
│ 1 byte │ 4 bytes │ N bytes             │
└───────┴──────────┴─────────────────────┘

MsgType:
  0x01 = PacketBatch (批量包摘要, MessagePack 编码)
  0x02 = PacketDetail (单包完整解码, JSON)
  0x03 = Stats (实时统计数据)
  0x04 = Error
```

### 5.2 分批推送策略

- 后端每 50ms 或累积 100 个包时批量推送
- 前端收到批次后追加到虚拟列表数据源
- 自动滚动跟随最新数据（可暂停）

## 6. 实时流接入方案

### 6.1 Android ADB 方案

**btsnoop 文件路径：**
- 固定路径：`/data/misc/bluetooth/logs/btsnoop_hci.log`
- 带时间戳路径：`/data/misc/bluetooth/logs/btsnoop_hci_*.log`（部分系统）

解析器应先尝试固定路径，失败后自动选取最新的带时间戳文件。

**开启抓包：**
```bash
# 方式一：开发者选项
设置 → 开发者选项 → 启用蓝牙 HCI 信息收集日志

# 方式二：命令行
adb shell settings put secure bluetooth_hci_log 1
adb shell svc bluetooth disable && adb shell svc bluetooth enable
```

**增量读取策略（来自 bt-snoop-live 验证）：**

```
┌─────────────────────────────────────────────────────────────┐
│  Proxy Agent 增量读取流程                                     │
│                                                              │
│  1. stat 获取当前文件大小 cur_size                            │
│  2. 若 cur_size < last_size → 文件已重置（蓝牙重启）         │
│     清空状态，重新从头读取                                    │
│  3. 若 cur_size > last_size → 有新数据                       │
│     - 首次(last_size==0)：拉取整个文件（含 16 字节 header）  │
│     - 增量：dd skip=last_size count=(cur_size-last_size)     │
│  4. 解析新数据中的 packet records                            │
│  5. 更新 last_size = cur_size                                │
│  6. sleep 500ms → 回到步骤 1                                 │
└─────────────────────────────────────────────────────────────┘
```

```bash
# 增量读取命令
adb shell "dd if=/data/misc/bluetooth/logs/btsnoop_hci.log bs=1 skip=${LAST_SIZE} count=${NEW_BYTES} 2>/dev/null"
```

**文件重置检测：**
当蓝牙服务重启时，btsnoop 文件会被截断或替换。检测条件：`cur_size < last_size`。此时需要：
- 清空 CID→PSM 映射表
- 清空连接状态表
- 重置包计数器
- 通知前端会话已重置

### 6.2 代理方案 (Proxy Agent)

```
┌──────────┐     ┌──────────────────┐     ┌────────────┐     ┌─────────┐
│  Phone   │────→│  Proxy Agent     │────→│  Web Server│────→│ Browser │
│ (ADB)    │     │  (PC端 Python)   │     │            │     │         │
└──────────┘     └──────────────────┘     └────────────┘     └─────────┘
                  │                  │
                  │ 轮询 stat 文件大小│
                  │ dd 增量读取       │
                  │ 解析 record      │
                  │ WebSocket 推送    │
                  └──────────────────┘
```

Proxy Agent 核心职责：
- 轮询文件大小（每 500ms）
- 增量读取新写入的 btsnoop record 数据
- 检测文件重置/轮转
- 通过 WebSocket 将原始 record 二进制流推送给 Web Server
- 支持 `-s SERIAL` 指定设备

**多设备支持：**
```bash
btsnoop-proxy --server ws://localhost:8080/ws/live --device auto    # 自动选第一个
btsnoop-proxy --server ws://localhost:8080/ws/live --device SERIAL  # 指定设备
```

### 6.3 嵌入式设备方案

对于可自定义固件的设备，在 HCI Transport 层插入 hook，直接将 HCI 数据通过网络上报。

### 6.4 轮询间隔与动态调整

| 场景         | 轮询间隔 | 说明                          |
|--------------|----------|-------------------------------|
| 实时调试     | 500ms    | 平衡延迟和 CPU 占用           |
| 后台监控     | 2000ms   | 低功耗场景                    |
| 高频流       | 200ms    | A2DP 流媒体期间              |

建议动态调整：连续 3 次无新数据时增大间隔，有新数据时恢复最小间隔。

## 7. 关键性能指标

| 指标                 | 目标值           |
|----------------------|------------------|
| 文件解析速度         | ≥ 100MB/s        |
| 单包解码延迟         | < 1ms            |
| 前端渲染帧率         | ≥ 60fps (10万包) |
| 实时流端到端延迟     | < 100ms          |
| 最大包容量           | ≥ 500万条        |
| 首屏渲染时间         | < 500ms          |

## 8. 安全设计

- 上传文件大小限制：默认 2GB
- 会话自动过期：30 分钟无活动后清理
- 无持久化存储用户数据
- 流式接入需要 Token 认证
- 支持私有部署

## 9. 扩展能力

### 9.1 协议插件机制

```rust
pub trait ProtocolDecoder {
    fn name(&self) -> &str;
    fn can_decode(&self, context: &DecodeContext) -> bool;
    fn decode(&self, data: &[u8], context: &DecodeContext) -> DecodeResult;
}
```

新协议通过实现 `ProtocolDecoder` trait 注册到解码栈，无需修改核心逻辑。

### 9.2 未来扩展方向

- [ ] 支持 pcap/pcapng 格式导入
- [ ] 协议流重组（L2CAP 分片重组、RFCOMM credit flow）
- [ ] 连接状态机可视化
- [ ] AI 辅助异常检测（断连原因分析、配对失败诊断）
- [ ] 导出为 Wireshark 兼容格式
- [ ] 对比两次抓包的差异
- [ ] 蓝牙 Profile 级语义解读 (A2DP codec negotiation, LE Audio BAP)

## 10. 开发阶段规划

| 阶段   | 内容                                        | 周期   |
|--------|---------------------------------------------|--------|
| P0     | btsnoop 解析 + HCI 解码 + 基础 Web UI       | 2 周   |
| P1     | L2CAP/ATT/SMP 解码 + 过滤引擎 + 虚拟列表   | 2 周   |
| P2     | 实时流接入 + RFCOMM/SDP/AVDTP 解码          | 2 周   |
| P3     | 性能优化 + 插件机制 + 协作功能              | 2 周   |

## 11. 参考资料

- Bluetooth Core Specification v5.4, Vol 4 Part A (HCI Transport)
- btsnoop format: https://www.fte.com/webhelp/bpa600/Content/Technical_Information/BT_Snoop_File_Format.htm
- Android Bluetooth HCI logging: AOSP `system/bt/hci/src/btsnoop.cc`
- Wireshark Bluetooth dissectors 源码
