# 连接状态机设计文档

## 1. 概述

btsnoop 解码中，L2CAP 动态 CID、AVDTP 流端点等上层协议依赖有状态的上下文信息。本文档定义各层状态机的状态、转移条件和解码器实现要求。

## 2. 为什么需要状态机

btsnoop 中大量数据包仅包含 CID/Handle 等数字标识，需要根据之前的信令交互才能确定它属于哪个协议。例如：

```
包 #100: L2CAP Connection Request PSM=0x0019(AVDTP) SCID=0x0041
包 #105: L2CAP Connection Response DCID=0x0050 SCID=0x0041 Result=Success
包 #200: L2CAP Data CID=0x0050 [payload...]
         ↑ 必须知道 CID 0x0050 对应 AVDTP 才能正确解码 payload
```

## 3. ACL 连接状态机

### 3.1 状态定义

```
                    Create_Connection CMD
    [Idle] ─────────────────────────────────→ [Connecting]
                                                    │
                              Connection_Complete    │
                              (status=0x00)         ▼
    [Disconnected] ←──────── [Connected] ←─────────┘
         ▲               │
         │               │ Disconnection_Complete
         └───────────────┘
```

| 状态          | 含义                     |
|---------------|--------------------------|
| Idle          | 无连接（初始状态）       |
| Connecting    | 已发出连接请求，等待完成 |
| Connected     | 连接已建立               |
| Disconnected  | 连接已断开               |

### 3.2 转移事件

| 事件                              | 源状态     | 目标状态      | 解码器动作                          |
|-----------------------------------|------------|---------------|-------------------------------------|
| HCI Create_Connection CMD         | Idle       | Connecting    | 记录目标 BD_ADDR                    |
| HCI Connection_Complete EVT (ok)  | Connecting | Connected     | 建立 handle→addr 映射              |
| HCI Connection_Complete EVT (fail)| Connecting | Idle          | 清理                                |
| HCI Disconnection_Complete EVT    | Connected  | Disconnected  | 标记断开时间和原因，保留历史映射    |
| LE_Connection_Complete            | -          | Connected     | 建立 handle→addr 映射 (BLE)        |
| LE_Enhanced_Connection_Complete   | -          | Connected     | 同上                                |

### 3.3 数据结构

```rust
struct AclConnectionState {
    handle: u16,
    address: [u8; 6],
    address_type: AddressType,  // Public / Random
    link_type: LinkType,        // ACL / LE
    state: ConnState,
    connected_at_index: u32,    // 建连包的序号
    disconnected_at_index: Option<u32>,
    disconnect_reason: Option<u8>,
}

// 全局映射
connections: HashMap<u16, AclConnectionState>
```

## 4. L2CAP 通道状态机

### 4.1 状态定义

```
                  CONN_REQ
    [Closed] ──────────────→ [Wait_Connect_Rsp]
        ▲                          │
        │                          │ CONN_RSP (result=Success)
        │                          ▼
        │                    [Config] ←─── CONFIG_REQ/RSP 交互
        │                          │
        │                          │ 双方 Config 完成
        │                          ▼
        │                    [Open]
        │                          │
        │     DISCONN_RSP          │ DISCONN_REQ
        └──────────────────────────┘
```

| 状态              | 含义                         |
|-------------------|------------------------------|
| Closed            | 通道未建立                   |
| Wait_Connect_Rsp  | 已发送 CONN_REQ，等待响应    |
| Config            | 连接已确认，正在配置         |
| Open              | 通道已打开，可传输数据       |
| Wait_Disconnect   | 已发送 DISCONN_REQ，等待响应 |

### 4.2 转移事件

| L2CAP 信令           | 动作                                              |
|---------------------|---------------------------------------------------|
| CONN_REQ            | 记录 PSM→SCID 映射，创建通道 (Wait_Connect_Rsp) |
| CONN_RSP (Success)  | 记录 DCID→SCID 映射，建立 CID→PSM 双向映射      |
| CONN_RSP (Pending)  | 保持 Wait_Connect_Rsp                            |
| CONN_RSP (Fail)     | 删除通道                                          |
| CONFIG_REQ          | 记录 MTU/Flush Timeout 等选项                    |
| CONFIG_RSP (Success)| 标记一侧配置完成，双方完成→Open                  |
| DISCONN_REQ         | 标记 Wait_Disconnect                              |
| DISCONN_RSP         | 删除通道，清理 CID 映射                          |

### 4.3 CID→PSM 映射规则

```
场景: 设备 A (Initiator) 连接 设备 B

1. A→B CONN_REQ: PSM=0x0019, SCID=0x0041
   → 记录: cid_map[0x0041] = PSM 0x0019 (AVDTP)

2. B→A CONN_RSP: DCID=0x0050, SCID=0x0041, Result=Success
   → 记录: cid_map[0x0050] = PSM 0x0019 (AVDTP)

3. 后续所有 CID=0x0041 或 CID=0x0050 的 L2CAP 数据包
   → 识别为 AVDTP 并分发到 AVDTP 解码器
```

**重要：** 双向 CID 都需要映射。发送方使用自己的 SCID 作为 Source CID，接收方使用 DCID。

### 4.4 固定 CID 无需状态机

| CID    | 协议    | 处理方式       |
|--------|---------|---------------|
| 0x0001 | L2CAP Signaling | 直接解码信令 |
| 0x0004 | ATT     | 直接分发到 ATT 解码器 |
| 0x0005 | LE L2CAP Signaling | 直接解码 |
| 0x0006 | SMP     | 直接分发到 SMP 解码器 |

### 4.5 数据结构

```rust
struct L2capChannelState {
    handle: u16,          // 所属 ACL 连接
    local_cid: u16,       // 本端 CID (SCID from CONN_REQ)
    remote_cid: u16,      // 对端 CID (DCID from CONN_RSP)
    psm: u16,
    protocol_name: String, // 根据 PSM 查表得到
    state: L2capState,
    local_mtu: u16,
    remote_mtu: u16,
    local_configured: bool,
    remote_configured: bool,
}

// PSM→Protocol 查表
fn psm_to_protocol(psm: u16) -> &str {
    match psm {
        0x0001 => "SDP",
        0x0003 => "RFCOMM",
        0x000F => "BNEP",
        0x0011 => "HID_Control",
        0x0013 => "HID_Interrupt",
        0x0017 => "AVCTP",
        0x0019 => "AVDTP",
        0x001B => "AVCTP_Browsing",
        _ => "Unknown",
    }
}

// CID 查找映射（核心数据结构）
// key: (acl_handle, cid) → L2capChannelState
channels: HashMap<(u16, u16), L2capChannelState>
```

## 5. AVDTP 流状态机

### 5.1 状态定义

```
                    DISCOVER
    [Idle] ──────────────────→ [Discovered]
                                     │
                          SET_CONFIGURATION
                                     ▼
                              [Configured]
                                     │
                                   OPEN
                                     ▼
                                [Open]
                                     │
                                   START
                                     ▼
                              [Streaming] ←── SUSPEND/START 可反复切换
                                     │
                                   CLOSE
                                     ▼
                              [Closing] → [Idle]
```

### 5.2 SEID 追踪

DISCOVER 响应中列出所有 Stream Endpoint (SEID)，后续 SET_CONFIGURATION/OPEN/START 等都通过 SEID 引用。解码器需要：

1. 记录 DISCOVER 响应中的 SEID 列表（包含 Media Type、TSEP）
2. SET_CONFIGURATION 时记录 ACP_SEID 和 INT_SEID 的绑定关系
3. 记录配置的 Codec 类型和参数
4. START/SUSPEND/CLOSE 时更新对应 SEID 的状态

### 5.3 数据结构

```rust
struct AvdtpEndpoint {
    seid: u8,
    media_type: MediaType,   // Audio/Video
    tsep: Tsep,              // Source/Sink
    in_use: bool,
    codec_type: Option<u8>,
    codec_info: Option<String>,  // 解析后的 codec 摘要
    state: AvdtpStreamState,
}

struct AvdtpSessionState {
    handle: u16,              // ACL handle
    l2cap_cid: u16,           // 信令通道 CID
    endpoints: HashMap<u8, AvdtpEndpoint>,  // SEID → Endpoint
    media_cid: Option<u16>,   // 媒体传输通道 CID (OPEN 后建立)
}
```

## 6. SMP 配对状态机

### 6.1 状态定义

```
    [Idle]
      │ Pairing_Request / Security_Request
      ▼
    [Pairing] ── Feature Exchange (IO Cap)
      │
      ▼
    [Key_Generation] ── Confirm/Random/Public Key/DHKey Check
      │
      ▼
    [Key_Distribution] ── LTK/IRK/CSRK 分发
      │
      ▼
    [Complete] (成功) 或 [Failed] (Pairing_Failed)
```

### 6.2 解码器关注点

SMP 状态机主要用于：
- 在摘要中显示当前配对阶段
- 识别 Legacy Pairing vs Secure Connections
- 识别配对方法（Just Works / Numeric Comparison / Passkey Entry）

## 7. 状态重建策略

### 7.1 文件解析模式

从文件第一个包开始顺序构建所有状态。每个包解码时更新状态表。

### 7.2 实时流模式

同文件模式。首次连接时从文件头开始，增量数据追加处理。

### 7.3 文件重置处理

当检测到 btsnoop 文件重置时（文件大小减小），必须：

```rust
fn reset_state(&mut self) {
    self.connections.clear();
    self.channels.clear();       // CID→PSM 映射
    self.avdtp_sessions.clear();
    self.packet_index = 0;
}
```

### 7.4 状态丢失容错

有时抓包从中间开始（错过了 CONN_REQ/RSP），此时：
- CID 无法映射到 PSM → 显示为 `L2CAP CID=0xNNNN (Unknown)`
- 不 panic，不报错，正常显示能解码的层级
- 如果后续出现该 CID 的信令，尝试恢复映射

## 8. 状态查询接口

前端和 API 层可查询当前状态：

```rust
// 获取所有活跃连接
fn get_active_connections(&self) -> Vec<&AclConnectionState>;

// 获取某连接上的所有通道
fn get_channels_for_handle(&self, handle: u16) -> Vec<&L2capChannelState>;

// 根据 CID 查协议名
fn resolve_protocol(&self, handle: u16, cid: u16) -> Option<&str>;

// 获取 AVDTP 流状态
fn get_avdtp_state(&self, handle: u16) -> Option<&AvdtpSessionState>;
```

## 9. 实现约束

1. 状态机更新必须在解码流水线中同步执行（顺序依赖）
2. 状态表只增不删（用状态标记关闭），保留历史信息供回溯
3. 查询接口必须是只读的（不修改状态）
4. 状态表的大小有上限：最多 256 个 ACL 连接 × 每连接 64 个通道
5. 单元测试需要覆盖：正常流程、乱序包、缺失信令、文件重置
