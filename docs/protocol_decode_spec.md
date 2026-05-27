# 协议解码规格文档

## 1. 概述

本文档定义各蓝牙协议层的解码规则、字段映射和展示格式。所有多字节字段除特别说明外均为 Little-Endian（btsnoop 头部除外，为 Big-Endian）。

## 2. HCI 层解码

### 2.1 HCI Command (0x01)

```
Offset  Size  Field
0       2     OpCode (OCF[9:0] | OGF[5:0] << 10)
2       1     Parameter Total Length
3       N     Parameters
```

**OpCode 解析:**
- OGF = (opcode >> 10) & 0x3F
- OCF = opcode & 0x03FF

**OGF 分组:**

| OGF  | 组名                          |
|------|-------------------------------|
| 0x01 | Link Control                  |
| 0x02 | Link Policy                   |
| 0x03 | Controller & Baseband         |
| 0x04 | Informational Parameters      |
| 0x05 | Status Parameters             |
| 0x06 | Testing                       |
| 0x08 | LE Controller                 |

**命令 OpCode 查表 (按 OGF 分组):**

**OGF 0x01 — Link Control:**

| OpCode | 命令名                    | 关键参数                                  |
|--------|---------------------------|-------------------------------------------|
| 0x0401 | Inquiry                   | LAP(3), Inquiry_Length(1), Num_Responses(1)|
| 0x0402 | Inquiry_Cancel            | (无参数)                                  |
| 0x0403 | Periodic_Inquiry          | Max_Period(2), Min_Period(2), LAP(3)...   |
| 0x0404 | Exit_Periodic_Inquiry     | (无参数)                                  |
| 0x0405 | Create_Connection         | BD_ADDR(6), Packet_Type(2), SR_Mode(1)...|
| 0x0406 | Disconnect                | Handle(2), Reason(1)                      |
| 0x0407 | Add_SCO_Connection        | Handle(2), Packet_Type(2)                 |
| 0x0408 | Accept_Connection         | BD_ADDR(6), Role(1)                       |
| 0x0409 | Reject_Connection         | BD_ADDR(6), Reason(1)                     |
| 0x040B | Link_Key_Reply            | BD_ADDR(6), Link_Key(16)                  |
| 0x040C | Link_Key_Neg_Reply        | BD_ADDR(6)                                |
| 0x040D | PIN_Code_Reply            | BD_ADDR(6), PIN_Length(1), PIN(16)        |
| 0x0411 | Authentication_Requested  | Handle(2)                                 |
| 0x0413 | Change_Conn_Pkt_Type      | Handle(2), Packet_Type(2)                 |
| 0x0419 | Remote_Name_Cancel        | BD_ADDR(6)                                |
| 0x041A | Remote_Name_Request       | BD_ADDR(6), SR_Mode(1)...                 |
| 0x041B | Read_Remote_Features      | Handle(2)                                 |
| 0x041C | Read_Remote_Ext_Features  | Handle(2), Page(1)                        |
| 0x041D | Read_Remote_Version       | Handle(2)                                 |
| 0x0428 | Setup_Sync_Conn           | Handle(2), Bandwidth(4)...                |
| 0x0429 | Accept_Sync_Conn          | BD_ADDR(6), Bandwidth(4)...               |
| 0x042B | IO_Capability_Reply       | BD_ADDR(6), IO(1), OOB(1), Auth(1)       |
| 0x042C | User_Confirm_Reply        | BD_ADDR(6)                                |
| 0x042D | User_Confirm_Neg_Reply    | BD_ADDR(6)                                |
| 0x0434 | IO_Capability_Neg_Reply   | BD_ADDR(6), Reason(1)                     |

**OGF 0x02 — Link Policy:**

| OpCode | 命令名                    | 关键参数                                  |
|--------|---------------------------|-------------------------------------------|
| 0x0801 | Hold_Mode                 | Handle(2), Max(2), Min(2)                 |
| 0x0803 | Sniff_Mode                | Handle(2), Max(2), Min(2), Attempt(2)...  |
| 0x0804 | Exit_Sniff                | Handle(2)                                 |
| 0x080D | Write_Link_Policy         | Handle(2), Policy(2)                      |
| 0x080F | Write_Default_Link_Policy | Policy(2)                                 |
| 0x0811 | Sniff_Subrating           | Handle(2), Max_Latency(2)...              |

**OGF 0x03 — Controller & Baseband:**

| OpCode | 命令名                    | 关键参数                                  |
|--------|---------------------------|-------------------------------------------|
| 0x0C01 | Set_Event_Mask            | Event_Mask(8)                             |
| 0x0C03 | Reset                     | (无参数)                                  |
| 0x0C05 | Set_Event_Filter          | Filter_Type(1), Condition(N)              |
| 0x0C08 | Flush                     | Handle(2)                                 |
| 0x0C13 | Change_Local_Name         | Name(248)                                 |
| 0x0C14 | Read_Local_Name           | (无参数)                                  |
| 0x0C1A | Write_Scan_Enable         | Scan_Enable(1)                            |
| 0x0C1C | Write_Page_Scan_Activity  | Interval(2), Window(2)                    |
| 0x0C1E | Write_Inquiry_Scan_Activity| Interval(2), Window(2)                   |
| 0x0C20 | Write_Auth_Enable         | Auth_Enable(1)                            |
| 0x0C24 | Write_Class_of_Device     | CoD(3)                                    |
| 0x0C25 | Read_Voice_Setting        | (无参数)                                  |
| 0x0C26 | Write_Voice_Setting       | Voice_Setting(2)                          |
| 0x0C33 | Host_Buffer_Size          | ACL_MTU(2), SCO_MTU(1), ACL_Pkts(2)...   |
| 0x0C35 | Read_Link_Supervision_TO  | Handle(2)                                 |
| 0x0C37 | Write_Link_Supervision_TO | Handle(2), Timeout(2)                     |
| 0x0C45 | Write_Inquiry_Mode        | Mode(1)                                   |
| 0x0C52 | Write_EIR                 | FEC_Required(1), EIR_Data(240)            |
| 0x0C56 | Write_Simple_Pairing      | Mode(1)                                   |
| 0x0C60 | Read_LE_Host_Support      | (无参数)                                  |
| 0x0C63 | Set_Event_Mask_Page2      | Event_Mask_Page_2(8)                      |
| 0x0C6D | Write_LE_Host_Support     | LE_Supported(1), Unused(1)                |
| 0x0C7A | Write_Secure_Conn_Support | Enable(1)                                 |
| 0x0C84 | Set_Min_Encryption_Key_Size| Key_Size(1)                              |

**OGF 0x04 — Informational:**

| OpCode | 命令名                    | 关键参数                                  |
|--------|---------------------------|-------------------------------------------|
| 0x1001 | Read_Local_Version        | (无参数)                                  |
| 0x1002 | Read_Local_Commands       | (无参数)                                  |
| 0x1003 | Read_Local_Features       | (无参数)                                  |
| 0x1004 | Read_Local_Ext_Features   | Page(1)                                   |
| 0x1005 | Read_Buffer_Size          | (无参数)                                  |
| 0x1009 | Read_BD_Addr              | (无参数)                                  |
| 0x100B | Read_Data_Block_Size      | (无参数)                                  |

**OGF 0x05 — Status:**

| OpCode | 命令名      | 关键参数   |
|--------|-------------|-----------|
| 0x1403 | Read_RSSI   | Handle(2) |

**OGF 0x08 — LE Controller:**

| OpCode | 命令名                    | 关键参数                                  |
|--------|---------------------------|-------------------------------------------|
| 0x2001 | LE_Set_Event_Mask         | LE_Event_Mask(8)                          |
| 0x2002 | LE_Read_Buffer_Size       | (无参数)                                  |
| 0x2003 | LE_Read_Local_Features    | (无参数)                                  |
| 0x2005 | LE_Set_Random_Addr        | Random_Address(6)                         |
| 0x2006 | LE_Set_Adv_Params         | Interval_Min(2), Interval_Max(2)...       |
| 0x2008 | LE_Set_Adv_Data           | Length(1), Data(31)                       |
| 0x200A | LE_Set_Adv_Enable         | Enable(1)                                 |
| 0x200C | LE_Set_Scan_Params        | Type(1), Interval(2), Window(2)...        |
| 0x200D | LE_Set_Scan_Enable        | Enable(1), Filter_Dup(1)                  |
| 0x200E | LE_Create_Connection      | Interval(2), Window(2), Policy(1)...      |
| 0x200F | LE_Read_White_List_Size   | (无参数)                                  |
| 0x201C | LE_Read_Supported_States  | (无参数)                                  |
| 0x2023 | LE_Read_Max_Data_Length   | (无参数)                                  |
| 0x202A | LE_Read_Num_Adv_Sets      | (无参数)                                  |
| 0x202F | LE_Read_TX_Power          | (无参数)                                  |
| 0x204A | LE_Read_Buffer_Size_V2    | (无参数)                                  |
| 0x2060 | LE_Set_Host_Feature       | Bit_Number(1), Bit_Value(1)               |

**OGF 0x3F — Vendor Specific (常见):**

| OpCode | 命令名 (厂商自定义)  | 说明             |
|--------|---------------------|------------------|
| 0xFC17 | VS_MTK_Init         | MediaTek 初始化  |
| 0xFD5D | VS_A2DP_Opcode      | A2DP 厂商扩展    |
| 0xFD95 | VS_Codec_State      | Codec 状态通知   |
| 0xFD53 | VS_MTK_Config       | MediaTek 配置    |

### 2.2 HCI Event (0x04)

```
Offset  Size  Field
0       1     Event Code
1       1     Parameter Total Length
2       N     Parameters
```

**事件码完整查表:**

| Code | 事件名                          | 关键参数                                  |
|------|--------------------------------|-------------------------------------------|
| 0x01 | Inquiry_Complete               | Status(1)                                 |
| 0x02 | Inquiry_Result                 | Num(1), BD_ADDR(6)×N...                  |
| 0x03 | Connection_Complete            | Status(1), Handle(2), BD_ADDR(6), Type(1)|
| 0x04 | Connection_Request             | BD_ADDR(6), CoD(3), Link_Type(1)         |
| 0x05 | Disconnection_Complete         | Status(1), Handle(2), Reason(1)          |
| 0x06 | Authentication_Complete        | Status(1), Handle(2)                     |
| 0x07 | Remote_Name_Complete           | Status(1), BD_ADDR(6), Name(248)         |
| 0x08 | Encryption_Change              | Status(1), Handle(2), Enabled(1)         |
| 0x09 | Change_Conn_Link_Key_Complete  | Status(1), Handle(2)                     |
| 0x0B | Read_Remote_Features_Complete  | Status(1), Handle(2), Features(8)        |
| 0x0C | Read_Remote_Version_Complete   | Status(1), Handle(2), Version(1)...      |
| 0x0E | Command_Complete               | Num_Pkts(1), OpCode(2), Return_Params(N) |
| 0x0F | Command_Status                 | Status(1), Num_Pkts(1), OpCode(2)        |
| 0x10 | Hardware_Error                 | Hardware_Code(1)                          |
| 0x12 | Role_Change                    | Status(1), BD_ADDR(6), Role(1)           |
| 0x13 | Num_Completed_Packets          | Num_Handles(1), Handle[](2×N), Num[](2×N)|
| 0x14 | Mode_Change                    | Status(1), Handle(2), Mode(1), Interval(2)|
| 0x17 | Link_Key_Notification          | BD_ADDR(6), Link_Key(16), Key_Type(1)    |
| 0x18 | Loopback_Command               | HCI_Command_Packet(N)                    |
| 0x1B | Max_Slots_Change               | Handle(2), Max_Slots(1)                  |
| 0x1C | Read_Clock_Offset_Complete     | Status(1), Handle(2), Offset(2)          |
| 0x1D | Conn_Pkt_Type_Changed          | Status(1), Handle(2), Pkt_Type(2)        |
| 0x20 | Page_Scan_Rep_Mode_Change      | BD_ADDR(6), Mode(1)                      |
| 0x22 | Inquiry_Result_With_RSSI       | Num(1), BD_ADDR(6)×N, RSSI(1)×N...      |
| 0x2F | Extended_Inquiry_Result        | Num(1), BD_ADDR(6), CoD(3), EIR(240)    |
| 0x30 | Encryption_Key_Refresh         | Status(1), Handle(2)                     |
| 0x31 | IO_Capability_Request          | BD_ADDR(6)                                |
| 0x32 | IO_Capability_Response         | BD_ADDR(6), IO(1), OOB(1), Auth(1)      |
| 0x33 | User_Confirm_Request           | BD_ADDR(6), Numeric_Value(4)             |
| 0x34 | User_Passkey_Request           | BD_ADDR(6)                                |
| 0x35 | Remote_OOB_Data_Request        | BD_ADDR(6)                                |
| 0x36 | Simple_Pairing_Complete        | Status(1), BD_ADDR(6)                    |
| 0x38 | Link_Supervision_TO_Changed    | Handle(2), Timeout(2)                    |
| 0x3E | LE_Meta_Event                  | Subevent_Code(1), ...                    |
| 0xFF | Vendor_Specific                | (厂商自定义)                              |

**Command_Complete 特殊解码:** 对 0x0E 事件，额外解析内嵌的 OpCode 和 Status，摘要格式为 `Cmd_Complete: {CMD_NAME} status={STATUS}`

**Command_Status 特殊解码:** 对 0x0F 事件，摘要格式为 `Cmd_Status: {CMD_NAME} status={STATUS}`

**Mode_Change 模式值:**

| 值 | 模式    |
|----|---------|
| 0  | Active  |
| 1  | Hold    |
| 2  | Sniff   |
| 3  | Park    |

**Disconnection Reason 常见值:**

| 值   | 含义                             |
|------|----------------------------------|
| 0x05 | Authentication Failure           |
| 0x08 | Connection Timeout               |
| 0x13 | Remote User Terminated           |
| 0x14 | Remote Device Low Resources      |
| 0x15 | Remote Device Power Off          |
| 0x16 | Connection Terminated by Local   |
| 0x1A | Unsupported Remote Feature       |
| 0x29 | Pairing with Unit Key Not Supported |
| 0x3B | Unacceptable Connection Parameters |

**LE Meta Event 子事件完整查表:**

| Subevent | 名称                              | 关键参数                          |
|----------|-----------------------------------|-----------------------------------|
| 0x01     | LE_Connection_Complete            | Status, Handle, Peer_Addr, Interval|
| 0x02     | LE_Advertising_Report             | Num_Reports, Event_Type, Addr, Data|
| 0x03     | LE_Connection_Update_Complete     | Status, Handle, Interval, Latency |
| 0x04     | LE_Read_Remote_Features_Complete  | Status, Handle, Features(8)       |
| 0x05     | LE_Long_Term_Key_Request          | Handle, Random(8), EDIV(2)        |
| 0x07     | LE_Data_Length_Change             | Handle, MaxTxOctets, MaxTxTime... |
| 0x08     | LE_Read_Local_P256_Key_Complete   | Status, Key(64)                   |
| 0x09     | LE_Generate_DHKey_Complete        | Status, DHKey(32)                 |
| 0x0A     | LE_Enhanced_Connection_Complete   | Status, Handle, Role, Addr...     |
| 0x0B     | LE_Directed_Advertising_Report    | Num_Reports, Event_Type, Addr...  |
| 0x0C     | LE_PHY_Update_Complete            | Status, Handle, TX_PHY, RX_PHY   |
| 0x0D     | LE_Extended_Advertising_Report    | Num_Reports, Event_Type, Addr...  |
| 0x0E     | LE_Periodic_Advertising_Sync_Established | Status, Handle, SID...   |
| 0x12     | LE_Channel_Selection_Algorithm    | Handle, Algorithm                 |
| 0x19     | LE_CIS_Established               | Status, Handle, CIG_Sync_Delay... |
| 0x1A     | LE_CIS_Request                    | ACL_Handle, CIS_Handle, CIG_ID...|
| 0x1B     | LE_Create_BIG_Complete            | Status, BIG_Handle, BIS_Handle... |
| 0x27     | LE_Subrate_Change                 | Status, Handle, Subrate_Factor... |

### 2.3 HCI ACL Data (0x02)

```
Offset  Size  Field
0       2     Handle(12bit) + PB_Flag(2bit) + BC_Flag(2bit)
2       2     Data Total Length
4       N     L2CAP Data
```

**PB Flag:**
| 值 | 含义                                |
|----|-------------------------------------|
| 0  | First non-automatically-flushable   |
| 1  | Continuing fragment                 |
| 2  | First automatically-flushable       |
| 3  | Complete L2CAP PDU                  |

### 2.4 HCI SCO Data (0x03)

```
Offset  Size  Field
0       2     Handle(12bit) + Packet_Status_Flag(2bit) + RFU(2bit)
2       1     Data Total Length
3       N     SCO Data
```

### 2.5 HCI ISO Data (0x05)

```
Offset  Size  Field
0       2     Handle(12bit) + PB_Flag(2bit) + TS_Flag(1bit) + RFU(1bit)
2       2     Data Load Length(14bit) + RFU(2bit)
4       4     Time_Stamp (if TS_Flag=1)
4/8     4     Packet_Sequence_Number(16bit) + ISO_SDU_Length(12bit) + RFU(2bit) + Packet_Status_Flag(2bit)
...     N     ISO SDU
```

## 3. L2CAP 层解码

### 3.1 Basic L2CAP Header

```
Offset  Size  Field
0       2     Length (payload size)
2       2     Channel ID (CID)
4       N     Information Payload
```

### 3.2 固定 CID

| CID    | 用途                    |
|--------|-------------------------|
| 0x0001 | L2CAP Signaling (BR/EDR)|
| 0x0002 | Connectionless          |
| 0x0003 | AMP Manager             |
| 0x0004 | ATT (BLE)               |
| 0x0005 | L2CAP Signaling (BLE)   |
| 0x0006 | SMP (BLE)               |
| 0x0007 | SMP (BR/EDR)            |
| ≥0x0040| 动态分配                |

### 3.3 L2CAP Signaling 命令

```
Offset  Size  Field
0       1     Code
1       1     Identifier
2       2     Length
4       N     Data
```

**命令码:**

| Code | 命令名                    |
|------|---------------------------|
| 0x01 | Command Reject            |
| 0x02 | Connection Request        |
| 0x03 | Connection Response       |
| 0x04 | Configuration Request     |
| 0x05 | Configuration Response    |
| 0x06 | Disconnection Request     |
| 0x07 | Disconnection Response    |
| 0x0A | Information Request       |
| 0x0B | Information Response      |
| 0x0C | Create Channel Request    |
| 0x0E | Move Channel Request      |
| 0x12 | Connection Parameter Update Request  |
| 0x13 | Connection Parameter Update Response |
| 0x14 | LE Credit Based Connection Request   |
| 0x17 | L2CAP Flow Control Credit  |

### 3.4 动态 CID → PSM 映射

解码器需维护连接状态表：

```
Connection Request (code=0x02):
  PSM → Source CID

Connection Response (code=0x03):
  Destination CID → Source CID → PSM
```

通过此映射确定动态 CID 对应的上层协议。

**常用 PSM:**

| PSM    | 协议        |
|--------|-------------|
| 0x0001 | SDP         |
| 0x0003 | RFCOMM      |
| 0x000F | BNEP        |
| 0x0017 | AVCTP       |
| 0x0019 | AVDTP       |
| 0x001F | ATT         |
| 0x0025 | EATT        |

## 4. ATT 协议解码

### 4.1 ATT PDU 格式

```
Offset  Size  Field
0       1     Opcode
1       N     Parameters
```

### 4.2 ATT Opcode 表

| Opcode | 方法                        | 参数格式                          |
|--------|-----------------------------|-----------------------------------|
| 0x01   | Error Response              | ReqOpcode(1), Handle(2), Error(1) |
| 0x02   | Exchange MTU Request        | Client Rx MTU(2)                  |
| 0x03   | Exchange MTU Response       | Server Rx MTU(2)                  |
| 0x04   | Find Information Request    | Start(2), End(2)                  |
| 0x05   | Find Information Response   | Format(1), Data(N)               |
| 0x08   | Read By Type Request        | Start(2), End(2), UUID(2/16)     |
| 0x09   | Read By Type Response       | Length(1), Data(N)               |
| 0x0A   | Read Request                | Handle(2)                         |
| 0x0B   | Read Response               | Value(N)                          |
| 0x10   | Read By Group Type Request  | Start(2), End(2), UUID(2/16)     |
| 0x11   | Read By Group Type Response | Length(1), Data(N)               |
| 0x12   | Write Request               | Handle(2), Value(N)              |
| 0x13   | Write Response              | (空)                              |
| 0x16   | Prepare Write Request       | Handle(2), Offset(2), Value(N)   |
| 0x18   | Execute Write Request       | Flags(1)                          |
| 0x1B   | Handle Value Notification   | Handle(2), Value(N)              |
| 0x1D   | Handle Value Indication     | Handle(2), Value(N)              |
| 0x1E   | Handle Value Confirmation   | (空)                              |
| 0x52   | Write Command               | Handle(2), Value(N)              |

### 4.3 ATT Error Code

| Code | 含义                          |
|------|-------------------------------|
| 0x01 | Invalid Handle                |
| 0x02 | Read Not Permitted            |
| 0x03 | Write Not Permitted           |
| 0x05 | Authentication Insufficient   |
| 0x06 | Request Not Supported         |
| 0x07 | Invalid Offset                |
| 0x0A | Attribute Not Found           |
| 0x0E | Unlikely Error                |

### 4.4 GATT Service Discovery 解读

解码器应识别标准 UUID 并显示可读名称：

| UUID   | 服务/特征名            |
|--------|------------------------|
| 0x1800 | Generic Access         |
| 0x1801 | Generic Attribute      |
| 0x180A | Device Information     |
| 0x180F | Battery Service        |
| 0x2A00 | Device Name            |
| 0x2A19 | Battery Level          |
| 0x2902 | CCCD                   |

## 5. SMP 协议解码

### 5.1 SMP PDU 格式

```
Offset  Size  Field
0       1     Code
1       N     Parameters
```

### 5.2 SMP 命令

| Code | 命令名              | 关键参数                                  |
|------|---------------------|-------------------------------------------|
| 0x01 | Pairing Request     | IO_Cap(1), OOB(1), AuthReq(1), Key_Size...|
| 0x02 | Pairing Response    | (同上)                                    |
| 0x03 | Pairing Confirm     | Confirm_Value(16)                         |
| 0x04 | Pairing Random      | Random_Value(16)                          |
| 0x05 | Pairing Failed      | Reason(1)                                 |
| 0x06 | Encryption Info     | LTK(16)                                   |
| 0x0B | Security Request    | AuthReq(1)                                |
| 0x0C | Pairing Public Key  | X(32), Y(32)                              |
| 0x0D | Pairing DHKey Check | DHKey_Check(16)                           |

### 5.3 IO Capability 解读

| 值 | 含义              |
|----|-------------------|
| 0  | DisplayOnly       |
| 1  | DisplayYesNo      |
| 2  | KeyboardOnly      |
| 3  | NoInputNoOutput   |
| 4  | KeyboardDisplay   |

## 6. SDP 协议解码

### 6.1 SDP PDU

```
Offset  Size  Field
0       1     PDU ID
1       2     Transaction ID
3       2     Parameter Length
5       N     Parameters
```

### 6.2 PDU ID

| ID   | 名称                         |
|------|------------------------------|
| 0x01 | SDP_ErrorResponse            |
| 0x02 | SDP_ServiceSearchRequest     |
| 0x03 | SDP_ServiceSearchResponse    |
| 0x04 | SDP_ServiceAttributeRequest  |
| 0x05 | SDP_ServiceAttributeResponse |
| 0x06 | SDP_ServiceSearchAttributeRequest  |
| 0x07 | SDP_ServiceSearchAttributeResponse |

### 6.3 Data Element 解析

SDP 使用 Type Descriptor + Size Descriptor + Value 的递归结构，解码器需递归解析并格式化输出。

## 7. RFCOMM 协议解码

### 7.1 RFCOMM Frame

```
Offset  Size  Field
0       1     Address (EA + C/R + DLCI)
1       1     Control (Frame Type)
2       1-2   Length (EA + Length)
...     N     Information
N+1     1     FCS
```

### 7.2 Frame Type

| 值   | 类型  | 含义          |
|------|-------|---------------|
| 0x2F | SABM  | 建立连接      |
| 0x63 | UA    | 确认          |
| 0x0F | DM    | 断开拒绝      |
| 0x43 | DISC  | 断开连接      |
| 0xEF | UIH   | 数据传输      |

### 7.3 DLCI 解析

- DLCI 0: 复用控制通道
- DLCI 1: 保留
- DLCI 2-61: 用户数据通道

## 8. AVDTP 协议解码

### 8.1 AVDTP Header

```
Bit:   [7  6] [5  4] [3  2  1  0]  [7  6  5  4  3  2  1  0]
Field: [TR  ] [Type ] [Label     ]  [Signal ID              ]
       Message Type   Transaction
```

### 8.2 Message Type

| 值 | 类型       |
|----|------------|
| 0  | Command    |
| 2  | Response Accept  |
| 3  | Response Reject  |

### 8.3 Signal ID

| ID   | 信令名              |
|------|---------------------|
| 0x01 | AVDTP_DISCOVER      |
| 0x02 | AVDTP_GET_CAPABILITIES |
| 0x03 | AVDTP_SET_CONFIGURATION |
| 0x04 | AVDTP_GET_CONFIGURATION |
| 0x05 | AVDTP_RECONFIGURE   |
| 0x06 | AVDTP_OPEN          |
| 0x07 | AVDTP_START         |
| 0x08 | AVDTP_CLOSE         |
| 0x09 | AVDTP_SUSPEND       |
| 0x0A | AVDTP_ABORT         |
| 0x0C | AVDTP_DELAY_REPORT  |

### 8.4 Service Capability 结构

AVDTP 的 GET_CAPABILITIES/SET_CONFIGURATION 等信令中携带 Capabilities 列表：

```
┌─────────────┬────────────┬─────────────────┐
│ Category ID │ LOSC       │ Category Data   │
│ (1 byte)    │ (1 byte)   │ (LOSC bytes)    │
└─────────────┴────────────┴─────────────────┘
重复直到数据结束
```

**Service Category ID:**

| ID   | 名称                | LOSC | 说明                    |
|------|---------------------|------|-------------------------|
| 0x01 | Media Transport     | 0    | 媒体传输（无参数）      |
| 0x02 | Reporting           | 0    | 报告能力                |
| 0x03 | Recovery            | 3    | 错误恢复                |
| 0x04 | Content Protection  | ≥2   | 内容保护                |
| 0x05 | Header Compression  | 1    | 头压缩                  |
| 0x06 | Multiplexing        | ≥2   | 多路复用                |
| 0x07 | Media Codec         | ≥2   | 媒体编解码器            |
| 0x08 | Delay Reporting     | 0    | 延迟报告                |

### 8.5 Content Protection (Category 0x04)

```
Offset  Size  Field
0       2     CP_Type (Little-Endian)
2       N     CP_Value (可选)
```

| CP_Type | 名称    |
|---------|---------|
| 0x0001  | DTCP    |
| 0x0002  | SCMS-T  |

### 8.6 Media Codec Capability (Category 0x07)

```
Offset  Size  Field
0       1     Media Type (高4位) + RFA (低4位)
1       1     Codec Type
2       N     Codec Specific Information
```

**Media Type:**

| 值 | 类型       |
|----|------------|
| 0  | Audio      |
| 1  | Video      |
| 2  | Multimedia |

**Codec Type:**

| 值   | 编码器     |
|------|-----------|
| 0x00 | SBC       |
| 0x01 | MPEG-1,2  |
| 0x02 | AAC       |
| 0x04 | ATRAC     |
| 0xFF | Vendor    |

### 8.7 DISCOVER Response 解码

DISCOVER RSP_ACCEPT 响应中包含 SEID 信息元素列表：

```
每 2 字节为一组：
Byte 0: SEID(6bit) + In_Use(1bit) + RFA(1bit)
Byte 1: Media_Type(4bit) + TSEP(1bit) + RFA(3bit)
```

| TSEP | 含义   |
|------|--------|
| 0    | Source |
| 1    | Sink   |

摘要输出示例：`DISCOVER RSP_ACCEPT [1(Audio/SRC) 2(Audio/SNK,InUse)]`

### 8.8 DELAY_REPORT 解码

```
Offset  Size  Field
0       1     SEID (高6位)
1       2     Delay (Big-Endian, 单位 1/10 ms)
```

摘要输出：`DELAY_REPORT CMD SEID=1 delay=20.0ms`

## 9. A2DP Codec Specific Information 解码

### 9.1 SBC (Codec Type = 0x00)

```
Octet 0 (高4位): Sampling Frequency
Octet 0 (低4位): Channel Mode
Octet 1 (高4位): Block Length
Octet 1 (低4位高2位): Subbands
Octet 1 (低2位): Allocation Method
Octet 2: Minimum Bitpool
Octet 3: Maximum Bitpool
```

**Sampling Frequency (位掩码):**

| Bit  | 频率    |
|------|---------|
| 0x80 | 16000   |
| 0x40 | 32000   |
| 0x20 | 44100   |
| 0x10 | 48000   |

**Channel Mode (位掩码):**

| Bit  | 模式          |
|------|---------------|
| 0x08 | Mono          |
| 0x04 | Dual Channel  |
| 0x02 | Stereo        |
| 0x01 | Joint Stereo  |

**Block Length (位掩码):**

| Bit  | 值 |
|------|-----|
| 0x80 | 4   |
| 0x40 | 8   |
| 0x20 | 12  |
| 0x10 | 16  |

**Subbands (位掩码):**

| Bit  | 值 |
|------|-----|
| 0x08 | 4   |
| 0x04 | 8   |

**Allocation Method (位掩码):**

| Bit  | 方法     |
|------|----------|
| 0x02 | SNR      |
| 0x01 | Loudness |

**摘要输出示例:** `SBC 44100Hz Joint bitpool=2-53`

### 9.2 AAC (Codec Type = 0x02)

```
Octet 0: Object Type (位掩码)
Octet 1: Sampling Frequency (高8位)
Octet 2 (高4位): Sampling Frequency (低4位)
Octet 2 (bit 3-2): Channels
Octet 3 (bit 7): VBR
Octet 3 (bit 6-0) + Octet 4 + Octet 5: Bit Rate (23位)
```

**Object Type (位掩码):**

| Bit  | 类型            |
|------|-----------------|
| 0x80 | MPEG-2 AAC LC   |
| 0x40 | MPEG-4 AAC LC   |
| 0x20 | MPEG-4 AAC LTP  |
| 0x10 | MPEG-4 AAC Scalable |

**Sampling Frequency (12位掩码，Octet1[7:0] + Octet2[7:4]):**

| Bit    | 频率   |
|--------|--------|
| 0x8000 | 8000   |
| 0x4000 | 11025  |
| 0x2000 | 12000  |
| 0x1000 | 16000  |
| 0x0800 | 22050  |
| 0x0400 | 24000  |
| 0x0200 | 32000  |
| 0x0100 | 44100  |
| 0x0080 | 48000  |
| 0x0040 | 64000  |
| 0x0020 | 88200  |
| 0x0010 | 96000  |

**Channels (Octet2 bit 3-2):**

| 值 | 模式    |
|----|---------|
| 1  | Mono    |
| 2  | Stereo  |

**摘要输出示例:** `AAC MPEG4-LC 48000Hz Stereo VBR 320kbps`

### 9.3 Vendor Codec (Codec Type = 0xFF)

```
Octet 0-3: Vendor ID (Little-Endian, 32位)
Octet 4-5: Vendor Codec ID (Little-Endian, 16位)
Octet 6+:  Codec Specific Information (厂商定义)
```

**已知 Vendor Codec 查表:**

| Vendor ID    | Codec ID | 编码器名称       |
|-------------|----------|------------------|
| 0x0000004F  | 0x0001   | aptX             |
| 0x000000D7  | 0x0024   | aptX HD          |
| 0x00000075  | 0x0102   | aptX Adaptive    |
| 0x00000075  | 0x0103   | aptX Lossless    |
| 0x0000012D  | 0x00AA   | LDAC             |
| 0x0000053A  | 0x4C32   | LHDC 2.0         |
| 0x0000053A  | 0x4C33   | LHDC 3.0/4.0     |
| 0x0000053A  | 0x4C35   | LHDC-V (5.x)     |
| 0x0000053A  | 0x4C48   | LHDC (通用)      |
| 0x0000000A  | 0x0001   | Samsung SSC      |

### 9.4 LDAC (Vendor ID=0x012D, Codec ID=0x00AA)

```
Octet 6: Sampling Frequency + Channel Mode (厂商自定义)
```

参考 LDAC 开源实现解码。

### 9.5 LHDC 2.0 / 3.0 / 4.0 (Vendor ID=0x053A, Codec ID=0x4C32/0x4C33)

#### Octet 6 (采样率 + 位深 + 特性):

```
Bit 7: LHDC-AR (自适应码率)
Bit 6: JAS (联合音频系统)
Bit 5: 16bit 支持
Bit 4: 24bit 支持
Bit 3: 44.1kHz 支持
Bit 2: 48kHz 支持
Bit 1: Reserved
Bit 0: 96kHz 支持
```

#### Octet 7 (特性 + 码率 + 版本):

```
Bit 7: LLAC 支持
Bit 6: LHDC-LL (低延迟) 支持
Bit 5-4: Max Bitrate
Bit 3-0: Version Number
```

**Max Bitrate (2位):**

| 值   | 码率    |
|------|---------|
| 0b00 | 900kbps |
| 0b01 | 500kbps |
| 0b10 | 400kbps |
| 0b11 | Reserved|

#### Octet 8 (仅 LHDC 4.0, Codec ID=0x4C33):

```
Bit 7: LHDC 4.0 标识
Bit 6: LARC (丢包恢复)
Bit 5-4: Min Bitrate (0=default, 1=320kbps)
Bit 3: 3rd Party (第三方协议)
Bit 2-0: Compressor Format
```

**Compressor Format:**

| 值 | 格式           |
|----|----------------|
| 0  | 无压缩         |
| 1  | Split TWS      |
| 2  | Split Pre L/R  |

**摘要输出示例:** `LHDC3.0/4.0 48K/96K 24bit max=900kbps [AR,JAS,LLAC,LL,V4.0,LARC]`

### 9.6 LHDC-V (Vendor ID=0x053A, Codec ID=0x4C35)

#### Octet 6 (采样率):

```
Bit 7-6: Reserved
Bit 5: 44.1kHz
Bit 4: 48kHz
Bit 3: Reserved
Bit 2: 96kHz
Bit 1: Reserved
Bit 0: 192kHz
```

#### Octet 7 (码率 + 位深):

```
Bit 7-6: Min Bitrate
Bit 5-4: Max Bitrate
Bit 3: Reserved
Bit 2: 16bit
Bit 1: 24bit
Bit 0: 32bit
```

**Max Bitrate (2位):**

| 值   | 码率      |
|------|-----------|
| 0b00 | No Limit  |
| 0b01 | 400kbps   |
| 0b10 | 600kbps   |
| 0b11 | 900kbps   |

**Min Bitrate (2位):**

| 值   | 码率      |
|------|-----------|
| 0b00 | No Limit  |
| 0b01 | 128kbps   |
| 0b10 | 256kbps   |
| 0b11 | 400kbps   |

#### Octet 8 (帧长 + 版本):

```
Bit 7-5: Reserved
Bit 4: 5ms 帧长支持
Bit 3-0: Version Number
```

**Version Number:**

| 值     | 版本  |
|--------|-------|
| 0b0001 | V5.0  |
| 0b0010 | V5.1  |
| 0b0100 | V5.2  |
| 0b1000 | V5.3  |

#### Octet 9 (高级特性):

```
Bit 7: Lossless 无损模式
Bit 6: LL 低延迟模式
Bit 5-3: Reserved
Bit 2: Meta 数据支持
Bit 1: JAS 联合音频系统
Bit 0: AR 自适应码率
```

**摘要输出示例:** `LHDC-V 48K/96K/192K 24bit/32bit max=900kbps min=NoLimit V5.2 5ms [Lossless,LL,JAS,AR]`

### 9.7 aptX / aptX HD

aptX 系列的 Codec Specific Information 较简单：

**aptX (Vendor ID=0x4F, Codec ID=0x0001):**
```
Octet 6: Sampling Frequency (高4位) + Channel Mode (低4位)
```

**aptX HD (Vendor ID=0xD7, Codec ID=0x0024):**
```
Octet 6: Sampling Frequency (高4位) + Channel Mode (低4位)
Octet 7-9: Reserved
```

Sampling Frequency / Channel Mode 位掩码与 SBC 定义相同。

### 9.8 aptX Adaptive (Vendor ID=0x75, Codec ID=0x0102)

```
Octet 6: Sampling Frequency (高4位) + Channel Mode (低4位)
Octet 7: TTP_LL_Low (低延迟目标时间低字节)
Octet 8: TTP_LL_High
Octet 9: TTP_HQ_Low (高质量目标时间低字节)
Octet 10: TTP_HQ_High
Octet 11: EOC (End of Codec info)
```

## 10. AVCTP/AVRCP 协议解码

### 9.1 AVCTP Header

```
Offset  Size  Field
0       1     Transaction Label(4bit) + Packet_Type(2bit) + C/R(1bit) + IPID(1bit)
1       2     Profile ID (0x110E = AVRCP)
```

### 9.2 AVRCP 常用 PDU

| PDU ID | 名称                      |
|--------|---------------------------|
| 0x10   | Get Capabilities          |
| 0x20   | Get Play Status           |
| 0x30   | Get Element Attributes    |
| 0x31   | Register Notification     |
| 0x48   | Set Absolute Volume       |
| 0x50   | Set Addressed Player      |

## 10. 解码输出规范

### 10.1 Summary 格式约定

每层协议输出一行摘要，格式：`{Protocol}: {Action/Type} {Key Info}`

示例：
```
HCI: Command HCI_LE_Set_Advertising_Parameters
HCI: Event Command_Complete (HCI_Reset) Status=Success
L2CAP: Connection Request PSM=AVDTP SCID=0x0041
ATT: Write Request Handle=0x0012 Value=0100
SMP: Pairing Request IO=DisplayYesNo
AVDTP: SET_CONFIGURATION SEID=1 Codec=SBC
AVRCP: Register Notification EVENT_PLAYBACK_STATUS_CHANGED
```

### 10.2 字段值展示规则

| 类型        | 格式                     | 示例              |
|-------------|--------------------------|-------------------|
| 整数        | 十进制                   | 42                |
| 位掩码/标志 | 0x前缀十六进制 + 名称    | 0x0E (Command Complete) |
| BD_ADDR     | 冒号分隔逆序             | AA:BB:CC:DD:EE:FF |
| UUID-16     | 0x前缀 + 已知名称        | 0x1800 (Generic Access) |
| UUID-128    | 标准格式                 | 12345678-1234-... |
| 原始数据    | 空格分隔十六进制         | 01 02 03 04       |
| ASCII 文本  | 引号包围                 | "MyDevice"        |
| 时间戳      | ISO 8601 + 相对时间      | 10:30:00.123 (+1.5ms) |
