# API 接口规格文档

## 1. 概述

本文档定义前后端所有通信接口，包含 REST API 和 WebSocket 协议。

Base URL: `http://{host}:{port}/api/v1`
WebSocket: `ws://{host}:{port}/ws`

## 2. REST API

### 2.1 会话管理

#### POST /session

创建新的解析会话。

**Request:**
```json
{
  "name": "optional session name",
  "mode": "file" | "live"
}
```

**Response:**
```json
{
  "session_id": "uuid-string",
  "ws_url": "ws://host:port/ws/session/{session_id}",
  "created_at": "2026-05-27T10:00:00Z",
  "expires_at": "2026-05-27T10:30:00Z"
}
```

#### GET /session/{session_id}

获取会话状态。

**Response:**
```json
{
  "session_id": "uuid",
  "status": "active" | "expired" | "closed",
  "packet_count": 12345,
  "duration_ms": 60000,
  "file_name": "btsnoop_hci.log",
  "file_size": 1048576
}
```

#### DELETE /session/{session_id}

关闭并清理会话。

**Response:**
```json
{
  "status": "closed"
}
```

### 2.2 文件上传

#### POST /session/{session_id}/upload

上传 btsnoop 文件，支持分块上传。

**Request:**
- Content-Type: `multipart/form-data`
- Field: `file` (btsnoop 文件)
- Field: `chunk_index` (可选，分块索引)
- Field: `total_chunks` (可选，总块数)

**Response:**
```json
{
  "status": "processing" | "complete",
  "packets_parsed": 5000,
  "progress_percent": 45.5
}
```

#### POST /session/{session_id}/stream

流式推送原始数据（用于实时模式）。

**Request:**
- Content-Type: `application/octet-stream`
- Body: 原始 btsnoop 二进制数据

**Response:**
```json
{
  "bytes_received": 4096,
  "packets_parsed": 12
}
```

### 2.3 数据包查询

#### GET /session/{session_id}/packets

分页获取包摘要列表。

**Query Parameters:**
| 参数       | 类型    | 必填 | 说明                |
|-----------|---------|------|---------------------|
| offset    | int     | 否   | 起始索引，默认 0    |
| limit     | int     | 否   | 数量，默认 100，最大 1000 |
| filter    | string  | 否   | 过滤表达式          |
| direction | string  | 否   | sent / received     |
| protocol  | string  | 否   | 协议名              |

**Response:**
```json
{
  "total": 50000,
  "filtered_total": 1200,
  "offset": 0,
  "packets": [
    {
      "index": 0,
      "timestamp": 1716800000000,
      "timestamp_relative_ms": 0.0,
      "direction": "sent",
      "type": "CMD",
      "protocol": "HCI",
      "summary": "HCI_Reset",
      "length": 3
    }
  ]
}
```

#### GET /session/{session_id}/packets/{index}

获取单个包完整解码详情。

**Response:**
```json
{
  "index": 42,
  "timestamp": 1716800000000,
  "direction": "received",
  "raw_hex": "040e0401030c00",
  "layers": [
    {
      "protocol": "HCI",
      "summary": "HCI Event: Command Complete (Reset)",
      "fields": [
        {
          "name": "Event Code",
          "value": "0x0e (Command Complete)",
          "offset": 0,
          "length": 1,
          "children": []
        },
        {
          "name": "Parameter Total Length",
          "value": 4,
          "offset": 1,
          "length": 1,
          "children": []
        },
        {
          "name": "Num HCI Command Packets",
          "value": 1,
          "offset": 2,
          "length": 1,
          "children": []
        },
        {
          "name": "Command OpCode",
          "value": "0x0C03 (HCI_Reset)",
          "offset": 3,
          "length": 2,
          "children": []
        },
        {
          "name": "Status",
          "value": "0x00 (Success)",
          "offset": 5,
          "length": 1,
          "children": []
        }
      ]
    }
  ]
}
```

### 2.4 统计信息

#### GET /session/{session_id}/stats

获取当前会话的统计摘要。

**Response:**
```json
{
  "total_packets": 50000,
  "total_bytes": 2048000,
  "duration_ms": 120000,
  "breakdown": {
    "by_type": {
      "command": 500,
      "event": 600,
      "acl": 48000,
      "sco": 900
    },
    "by_direction": {
      "sent": 25000,
      "received": 25000
    },
    "by_protocol": {
      "HCI": 1100,
      "L2CAP": 48000,
      "ATT": 20000,
      "SDP": 500,
      "RFCOMM": 5000,
      "AVDTP": 22500
    }
  },
  "connections": [
    {
      "handle": 1,
      "address": "AA:BB:CC:DD:EE:FF",
      "type": "ACL",
      "packets": 30000
    }
  ]
}
```

### 2.5 过滤

#### POST /session/{session_id}/filter/validate

验证过滤表达式语法。

**Request:**
```json
{
  "expression": "hci.type == acl && l2cap.cid == 0x0004"
}
```

**Response:**
```json
{
  "valid": true,
  "parsed_tree": "AND(EQ(hci.type, acl), EQ(l2cap.cid, 0x0004))",
  "error": null
}
```

### 2.6 导出

#### GET /session/{session_id}/export

导出解析结果。

**Query Parameters:**
| 参数   | 类型   | 说明                              |
|--------|--------|-----------------------------------|
| format | string | json / csv / pcapng / text        |
| filter | string | 可选，仅导出匹配包               |

**Response:** 文件下载流

## 3. WebSocket 协议

### 3.1 连接

```
GET ws://{host}:{port}/ws/session/{session_id}
Headers:
  Authorization: Bearer {token}  (可选)
```

### 3.2 客户端 → 服务端消息

```typescript
// 设置过滤器
{
  "type": "set_filter",
  "expression": "att.opcode == 0x12"
}

// 请求包详情
{
  "type": "get_detail",
  "index": 42
}

// 控制自动滚动
{
  "type": "control",
  "action": "pause" | "resume"
}

// 上传数据块 (Binary Frame)
// 直接发送二进制数据，无 JSON 包装
```

### 3.3 服务端 → 客户端消息

```typescript
// 新包批次
{
  "type": "packet_batch",
  "packets": [ PacketSummary... ],
  "total": 50100
}

// 包详情响应
{
  "type": "packet_detail",
  "data": { ...full decoded packet... }
}

// 统计更新
{
  "type": "stats_update",
  "stats": { ...stats object... }
}

// 解析进度
{
  "type": "progress",
  "percent": 75.5,
  "packets_parsed": 37500
}

// 错误
{
  "type": "error",
  "code": "INVALID_FORMAT",
  "message": "Not a valid btsnoop file"
}
```

### 3.4 心跳

- 客户端每 30s 发送 WebSocket Ping
- 服务端 60s 未收到 Ping 则关闭连接

## 4. 错误码

| HTTP Status | Code              | 说明                   |
|-------------|-------------------|------------------------|
| 400         | INVALID_FORMAT    | 非法 btsnoop 文件格式  |
| 400         | INVALID_FILTER    | 过滤表达式语法错误     |
| 404         | SESSION_NOT_FOUND | 会话不存在或已过期     |
| 413         | FILE_TOO_LARGE    | 文件超过大小限制       |
| 429         | RATE_LIMITED      | 请求过于频繁           |
| 500         | INTERNAL_ERROR    | 服务端内部错误         |

## 5. 限制约束

| 项目               | 限制值       |
|--------------------|-------------|
| 单文件最大大小     | 2 GB        |
| 单会话最大包数     | 500 万条    |
| 会话过期时间       | 30 分钟     |
| WebSocket 消息大小 | 1 MB        |
| 并发会话数         | 100         |
| 单批次推送包数     | 100 条      |
| 过滤表达式最大长度 | 1024 字符   |
