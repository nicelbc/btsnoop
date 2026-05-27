# 数据结构设计文档

## 1. 概述

本文档定义系统运行时的核心数据结构，包括内存存储模型、索引设计和会话管理。

## 2. 核心数据模型

### 2.1 Session（会话）

```rust
pub struct Session {
    pub id: Uuid,
    pub name: Option<String>,
    pub mode: SessionMode,
    pub status: SessionStatus,
    pub created_at: DateTime<Utc>,
    pub last_active: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
    pub file_info: Option<FileInfo>,
    pub packets: PacketStore,
    pub connection_state: ConnectionStateMap,
    pub stats: SessionStats,
}

pub enum SessionMode {
    File,   // 文件上传解析
    Live,   // 实时流模式
}

pub enum SessionStatus {
    Active,
    Parsing,
    Paused,
    Expired,
    Closed,
}

pub struct FileInfo {
    pub name: String,
    pub size: u64,
    pub datalink_type: u32,
    pub btsnoop_version: u32,
}
```

### 2.2 Packet（数据包）

```rust
pub struct RawPacket {
    pub index: u32,
    pub original_length: u32,
    pub included_length: u32,
    pub flags: u32,
    pub cumulative_drops: u32,
    pub timestamp_us: i64,          // btsnoop 原始时间戳
    pub unix_timestamp_us: i64,     // 转换后的 Unix 时间戳
    pub data: Vec<u8>,              // 原始字节
}

pub struct PacketSummary {
    pub index: u32,
    pub timestamp_us: i64,
    pub relative_time_ms: f64,      // 相对于第一个包的时间
    pub direction: Direction,
    pub hci_type: HciType,
    pub protocol: String,           // 最高层协议名
    pub summary: String,            // 单行摘要文本
    pub length: u16,
}

pub enum Direction {
    Sent,       // Host → Controller
    Received,   // Controller → Host
}

pub enum HciType {
    Command,
    AclData,
    ScoData,
    Event,
    IsoData,
}
```

### 2.3 解码结果

```rust
pub struct DecodedPacket {
    pub index: u32,
    pub raw: RawPacket,
    pub layers: Vec<DecodedLayer>,
}

pub struct DecodedLayer {
    pub protocol: String,
    pub summary: String,
    pub fields: Vec<DecodedField>,
    pub payload_offset: usize,
    pub payload_length: usize,
    pub errors: Vec<String>,        // 解码异常/警告
}

pub struct DecodedField {
    pub name: String,
    pub value: FieldValue,
    pub offset: usize,              // 在原始包中的字节偏移
    pub length: usize,
    pub display: String,            // 格式化显示文本
    pub children: Vec<DecodedField>,
}

pub enum FieldValue {
    Uint(u64),
    Int(i64),
    Bytes(Vec<u8>),
    String(String),
    Bool(bool),
    Enum { raw: u64, name: String },
    BitMask { raw: u64, flags: Vec<String> },
    Address([u8; 6]),
    Uuid16(u16),
    Uuid128([u8; 16]),
}
```

## 3. 存储设计

### 3.1 PacketStore（包存储）

```rust
pub struct PacketStore {
    summaries: Vec<PacketSummary>,       // 摘要数组，内存常驻
    raw_data: Vec<RawPacket>,            // 原始数据，内存常驻
    decoded_cache: LruCache<u32, DecodedPacket>,  // 解码缓存，LRU 淘汰
    first_timestamp: Option<i64>,        // 第一个包时间戳（算相对时间）
}
```

**内存估算:**

| 组件         | 单包大小    | 100万包    | 500万包    |
|--------------|-------------|------------|------------|
| PacketSummary| ~120 bytes  | ~120 MB    | ~600 MB    |
| RawPacket    | ~200 bytes (avg) | ~200 MB | ~1 GB    |
| DecodedCache | ~2 KB/entry | 20 MB (1万条) | 20 MB  |
| **总计**     |             | ~340 MB    | ~1.6 GB    |

### 3.2 索引设计

```rust
pub struct PacketIndex {
    // 按类型索引
    by_type: HashMap<HciType, Vec<u32>>,

    // 按连接句柄索引
    by_handle: HashMap<u16, Vec<u32>>,

    // 按协议索引
    by_protocol: HashMap<String, Vec<u32>>,

    // 按方向索引
    sent_indices: Vec<u32>,
    received_indices: Vec<u32>,

    // 时间范围索引（分桶，每桶1秒）
    time_buckets: BTreeMap<i64, Vec<u32>>,
}
```

### 3.3 过滤结果缓存

```rust
pub struct FilterCache {
    // key: 过滤表达式的 hash
    cache: HashMap<u64, FilterResult>,
    max_entries: usize,
}

pub struct FilterResult {
    pub expression: String,
    pub matched_indices: Vec<u32>,
    pub created_at: Instant,
    pub packet_count_at_creation: u32,  // 创建时的总包数（增量更新用）
}
```

## 4. 连接状态追踪

### 4.1 连接状态表

解码 L2CAP 动态通道和上层协议需要维护有状态信息：

```rust
pub struct ConnectionStateMap {
    // ACL 连接: handle → 连接信息
    acl_connections: HashMap<u16, AclConnection>,

    // L2CAP 通道: (handle, cid) → 通道信息
    l2cap_channels: HashMap<(u16, u16), L2capChannel>,
}

pub struct AclConnection {
    pub handle: u16,
    pub address: [u8; 6],
    pub address_type: AddressType,
    pub link_type: LinkType,
    pub established_at: i64,
    pub disconnected_at: Option<i64>,
}

pub struct L2capChannel {
    pub handle: u16,
    pub local_cid: u16,
    pub remote_cid: u16,
    pub psm: u16,
    pub protocol: String,       // 根据 PSM 映射的协议名
    pub state: ChannelState,
    pub mtu: u16,
}

pub enum ChannelState {
    Connecting,
    Open,
    Disconnecting,
    Closed,
}
```

### 4.2 状态更新触发

| HCI/L2CAP 事件               | 状态更新操作                        |
|-------------------------------|-------------------------------------|
| Connection_Complete Event     | 创建 AclConnection                  |
| Disconnection_Complete Event  | 标记 AclConnection 断开             |
| L2CAP Connection Request      | 创建 L2capChannel (Connecting)      |
| L2CAP Connection Response     | 更新 remote_cid，状态→Open          |
| L2CAP Disconnection Request   | 状态→Disconnecting                  |
| L2CAP Disconnection Response  | 状态→Closed                         |
| L2CAP Configuration Request   | 更新 MTU 等配置                     |

## 5. 会话管理

### 5.1 会话生命周期

```
Created → Active → Expired/Closed
              ↕
           Parsing (文件解析中)
```

### 5.2 SessionManager

```rust
pub struct SessionManager {
    sessions: RwLock<HashMap<Uuid, Arc<RwLock<Session>>>>,
    config: SessionConfig,
}

pub struct SessionConfig {
    pub max_sessions: usize,                // 最大并发会话数
    pub session_timeout: Duration,          // 会话超时时间
    pub max_packets_per_session: u32,       // 单会话最大包数
    pub max_file_size: u64,                 // 最大文件大小
    pub cleanup_interval: Duration,         // 清理检查间隔
    pub decoded_cache_size: usize,          // 解码缓存条目数
}
```

### 5.3 过期清理

- 定时任务每 60s 扫描过期会话
- 会话过期条件：`now - last_active > session_timeout`
- 清理动作：释放 PacketStore、关闭 WebSocket 连接

## 6. 前端状态模型

### 6.1 全局 Store

```typescript
interface AppState {
  session: SessionState;
  packets: PacketState;
  ui: UIState;
}

interface SessionState {
  id: string | null;
  status: "idle" | "connecting" | "active" | "expired";
  mode: "file" | "live";
  stats: SessionStats | null;
}

interface PacketState {
  summaries: PacketSummary[];    // 所有包摘要
  totalCount: number;
  filteredIndices: number[];     // 过滤后的索引
  selectedIndex: number | null;
  selectedDetail: DecodedPacket | null;
  filter: string;
  autoScroll: boolean;
}

interface UIState {
  theme: "light" | "dark";
  layout: LayoutConfig;
  columnWidths: Record<string, number>;
  expandedFields: Set<string>;  // 协议树展开状态
}
```

### 6.2 前端内存管理

当包数量超过阈值时的降级策略：

| 包数量        | 策略                                    |
|---------------|----------------------------------------|
| < 10万        | 全量保持在内存                          |
| 10万 ~ 100万  | 仅保留摘要，详情按需请求              |
| > 100万       | 摘要分页加载，旧数据从前端内存释放    |

## 7. 并发模型

### 7.1 后端线程模型

```
Main Thread (Tokio Runtime)
├── HTTP Handler Threads
├── WebSocket Handler (per connection)
├── Parser Thread (per session, blocking work)
│   └── 解析 → 解码 → 写入 PacketStore → 通知 WS
└── Cleanup Timer Thread
```

### 7.2 锁策略

| 资源             | 锁类型     | 说明                          |
|------------------|-----------|-------------------------------|
| SessionManager   | RwLock    | 读多写少                      |
| Session          | RwLock    | 解析写、查询读                |
| PacketStore      | RwLock    | append-only，读无锁（原子长度）|
| ConnectionState  | Mutex     | 解析时顺序更新                |
| FilterCache      | RwLock    | 缓存命中读、miss 时写         |
