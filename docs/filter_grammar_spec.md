# 过滤引擎语法规格文档

## 1. 概述

本文档定义过滤表达式的完整语法规则，采用 PEG (Parsing Expression Grammar) 描述。过滤引擎对每个数据包执行布尔匹配，返回 true/false。

## 2. 语法定义 (PEG)

```peg
// 顶层规则
Expression   ← OrExpr EOF
OrExpr       ← AndExpr (OR AndExpr)*
AndExpr      ← UnaryExpr (AND UnaryExpr)*
UnaryExpr    ← NOT? PrimaryExpr
PrimaryExpr  ← Comparison / Contains / Exists / '(' OrExpr ')'

// 比较表达式
Comparison   ← FieldPath CompOp Value
CompOp       ← '==' / '!=' / '>' / '>=' / '<' / '<='
FieldPath    ← Identifier ('.' Identifier)*
Value        ← HexNumber / DecNumber / String / Identifier

// 文本搜索
Contains     ← ('contains' / 'CONTAINS') String
               / FieldPath ('contains' / 'CONTAINS') String

// 字段存在性检查
Exists       ← FieldPath

// 逻辑运算符
AND          ← '&&' / 'and' / 'AND'
OR           ← '||' / 'or' / 'OR'
NOT          ← '!' / 'not' / 'NOT'

// 基础类型
Identifier   ← [a-zA-Z_][a-zA-Z0-9_]*
HexNumber    ← '0x' [0-9a-fA-F]+
DecNumber    ← [0-9]+
String       ← '"' [^"]* '"'
```

## 3. 字段命名空间

### 3.1 顶层字段

| 字段            | 类型    | 说明                  |
|-----------------|---------|----------------------|
| direction       | enum    | sent / received      |
| index           | uint    | 包序号               |
| length          | uint    | 包长度               |
| timestamp       | uint    | 时间戳 (微秒)       |

### 3.2 HCI 命名空间 (hci.*)

| 字段            | 类型    | 说明                      |
|-----------------|---------|--------------------------|
| hci.type        | enum    | command/event/acl/sco/iso |
| hci.opcode      | uint16  | 命令 OpCode              |
| hci.ogf         | uint8   | OpCode Group Field       |
| hci.ocf         | uint16  | OpCode Command Field     |
| hci.event       | uint8   | 事件码                   |
| hci.subevent    | uint8   | 子事件码 (LE Meta)       |
| hci.handle      | uint16  | 连接句柄                 |
| hci.status      | uint8   | 状态码                   |

### 3.3 L2CAP 命名空间 (l2cap.*)

| 字段            | 类型    | 说明                 |
|-----------------|---------|---------------------|
| l2cap.cid       | uint16  | Channel ID          |
| l2cap.length    | uint16  | Payload 长度        |
| l2cap.psm       | uint16  | PSM                 |
| l2cap.code      | uint8   | Signaling 命令码    |
| l2cap.scid      | uint16  | Source CID          |
| l2cap.dcid      | uint16  | Destination CID     |

### 3.4 ATT 命名空间 (att.*)

| 字段            | 类型    | 说明                 |
|-----------------|---------|---------------------|
| att.opcode      | uint8   | ATT 操作码          |
| att.handle      | uint16  | Attribute Handle    |
| att.error       | uint8   | Error Code          |
| att.mtu         | uint16  | MTU 值              |
| att.uuid        | uuid    | UUID 值             |
| att.value       | bytes   | Attribute Value     |

### 3.5 SMP 命名空间 (smp.*)

| 字段            | 类型    | 说明                 |
|-----------------|---------|---------------------|
| smp.code        | uint8   | SMP 命令码          |
| smp.io_cap      | uint8   | IO Capability       |
| smp.auth_req    | uint8   | Auth Requirements   |
| smp.reason      | uint8   | Pairing Failed 原因 |

### 3.6 SDP 命名空间 (sdp.*)

| 字段            | 类型    | 说明                 |
|-----------------|---------|---------------------|
| sdp.pdu_id      | uint8   | PDU ID              |
| sdp.tid         | uint16  | Transaction ID      |

### 3.7 RFCOMM 命名空间 (rfcomm.*)

| 字段            | 类型    | 说明                 |
|-----------------|---------|---------------------|
| rfcomm.dlci     | uint8   | DLCI                |
| rfcomm.type     | enum    | sabm/ua/dm/disc/uih |
| rfcomm.cr       | bool    | Command/Response    |

### 3.8 AVDTP 命名空间 (avdtp.*)

| 字段            | 类型    | 说明                 |
|-----------------|---------|---------------------|
| avdtp.signal    | uint8   | Signal ID           |
| avdtp.msg_type  | enum    | command/accept/reject|
| avdtp.seid      | uint8   | Stream Endpoint ID  |

### 3.9 AVRCP 命名空间 (avrcp.*)

| 字段             | 类型    | 说明                |
|-----------------|---------|---------------------|
| avrcp.pdu_id    | uint8   | PDU ID              |
| avrcp.event_id  | uint8   | Notification Event  |

### 3.10 通用字段 (bt.*)

| 字段            | 类型    | 说明                 |
|-----------------|---------|---------------------|
| bt.addr         | addr    | 蓝牙地址            |
| bt.protocol     | string  | 最高层协议名        |

## 4. 枚举值别名

为提升易用性，以下枚举值支持名称引用：

### 4.1 hci.type

| 名称       | 等价数值 |
|-----------|----------|
| command   | 0x01     |
| acl       | 0x02     |
| sco       | 0x03     |
| event     | 0x04     |
| iso       | 0x05     |

### 4.2 att.opcode

| 名称               | 等价数值 |
|--------------------|----------|
| error_rsp          | 0x01     |
| mtu_req            | 0x02     |
| mtu_rsp            | 0x03     |
| find_info_req      | 0x04     |
| find_info_rsp      | 0x05     |
| read_by_type_req   | 0x08     |
| read_by_type_rsp   | 0x09     |
| read_req           | 0x0A     |
| read_rsp           | 0x0B     |
| read_by_group_req  | 0x10     |
| read_by_group_rsp  | 0x11     |
| write_req          | 0x12     |
| write_rsp          | 0x13     |
| write_cmd          | 0x52     |
| notification       | 0x1B     |
| indication         | 0x1D     |
| confirmation       | 0x1E     |

### 4.3 direction

| 名称      | 含义              |
|-----------|-------------------|
| sent      | Host→Controller   |
| received  | Controller→Host   |

## 5. 运算符优先级

从高到低：

| 优先级 | 运算符      | 结合性 |
|--------|------------|--------|
| 1      | NOT (!)    | 右     |
| 2      | AND (&&)   | 左     |
| 3      | OR (\|\|) | 左     |

括号可改变优先级。

## 6. 类型转换规则

| 比较场景           | 规则                                    |
|--------------------|----------------------------------------|
| uint == hex        | 直接比较                                |
| enum == string     | 字符串映射为枚举值后比较                |
| addr == string     | 解析字符串为 6 字节地址后比较           |
| uuid == hex/string | 统一转为 128bit 比较                    |
| bytes contains str | 将 str 解释为 hex 序列或 ASCII 后搜索  |

## 7. 语义规则

### 7.1 字段不存在

当包中不包含某协议层时，相关字段引用返回 `null`，任何与 `null` 的比较结果为 `false`。

```
att.opcode == 0x12
// 对于非 ATT 包，结果为 false（不报错）
```

### 7.2 字段存在性检查

直接引用字段路径作为布尔表达式：

```
att              // true if packet contains ATT layer
l2cap.psm        // true if L2CAP has PSM field (signaling)
```

### 7.3 Contains 语义

```
contains "text"           // 在整个包的 summary 中搜索
att.value contains "AB"   // 在 ATT value 字段中搜索 hex 序列 0xAB
```

## 8. 错误处理

| 错误类型        | 示例                   | 处理方式                |
|-----------------|------------------------|------------------------|
| 语法错误        | `hci.type ==`          | 返回解析错误位置       |
| 未知字段        | `hci.foo == 1`         | 返回字段不存在提示     |
| 类型不匹配      | `hci.type > 5`         | 返回类型不支持此运算符 |
| 无效枚举值      | `hci.type == xxx`      | 返回合法枚举值列表     |

错误响应格式：

```json
{
  "valid": false,
  "error": {
    "message": "Unknown field: hci.foo",
    "position": 0,
    "length": 7,
    "suggestions": ["hci.type", "hci.opcode", "hci.handle"]
  }
}
```

## 9. 性能约束

| 约束项               | 限制值    |
|---------------------|-----------|
| 表达式最大长度       | 1024 字符 |
| 最大嵌套深度         | 16 层     |
| 最大 OR 分支数       | 32        |
| 单次过滤超时         | 10 秒     |
| 编译后过滤函数缓存数 | 64 条     |

## 10. 实现要点

### 10.1 编译型过滤

过滤表达式解析后编译为 `Fn(&Packet) -> bool` 闭包，避免每包重复解析 AST。

```rust
pub fn compile(expression: &str) -> Result<Box<dyn Fn(&Packet) -> bool>, FilterError>
```

### 10.2 快速路径

对常见过滤模式走快速路径：
- `hci.type == X` → 直接查索引，不遍历
- `hci.handle == X` → 直接查索引
- `direction == X` → 直接查索引

### 10.3 增量过滤

新包到达时，对新包执行已激活的过滤表达式，追加到已有结果。不重新遍历全部数据。
