# 测试规范文档

## 1. 概述

本文档定义测试策略、测试用例设计规范和测试执行要求。所有功能代码必须有对应测试覆盖，所有变更必须通过全量测试后才可合入。

## 2. 测试分层

```
┌─────────────────────────────────────┐
│         E2E Tests (端到端)           │  少量关键路径
├─────────────────────────────────────┤
│       Integration Tests (集成)       │  API + WebSocket
├─────────────────────────────────────┤
│         Unit Tests (单元)            │  解码器、过滤器、工具函数
└─────────────────────────────────────┘
```

| 层级      | 占比  | 运行时间目标 | 运行时机         |
|-----------|-------|-------------|-----------------|
| 单元测试   | 70%  | < 30s       | 每次 commit      |
| 集成测试   | 20%  | < 2min      | 每次 PR          |
| E2E 测试  | 10%  | < 5min      | merge 前 / 发版前 |

## 3. 后端测试规范

### 3.1 解码器单元测试

每个协议解码器必须覆盖以下测试类别：

#### 3.1.1 HCI 解码器测试用例

```rust
#[cfg(test)]
mod tests {
    use super::*;

    // ===== 正常用例 =====

    #[test]
    fn test_decode_hci_reset_command() {
        // HCI_Reset command: opcode=0x0C03, len=0
        let data = &[0x03, 0x0C, 0x00];
        let result = decode_hci_command(data).unwrap();
        assert_eq!(result.opcode, 0x0C03);
        assert_eq!(result.ogf, 0x03);
        assert_eq!(result.ocf, 0x0003);
        assert_eq!(result.summary, "HCI_Reset");
        assert_eq!(result.params.len(), 0);
    }

    #[test]
    fn test_decode_hci_disconnect_command() {
        // Disconnect: handle=0x0001, reason=0x13 (Remote User Terminated)
        let data = &[0x06, 0x04, 0x03, 0x01, 0x00, 0x13];
        let result = decode_hci_command(data).unwrap();
        assert_eq!(result.opcode, 0x0406);
        assert_eq!(result.params["handle"], 0x0001);
        assert_eq!(result.params["reason"], 0x13);
    }

    #[test]
    fn test_decode_hci_command_complete_event() {
        // Command Complete for HCI_Reset, status=0x00
        let data = &[0x0E, 0x04, 0x01, 0x03, 0x0C, 0x00];
        let result = decode_hci_event(data).unwrap();
        assert_eq!(result.event_code, 0x0E);
        assert_eq!(result.summary, "Command Complete (HCI_Reset) Status=Success");
    }

    #[test]
    fn test_decode_hci_connection_complete_event() {
        // Connection Complete: status=0, handle=0x000B, addr, type=ACL
        let data = &[0x03, 0x0B, 0x00, 0x0B, 0x00,
                     0x11, 0x22, 0x33, 0x44, 0x55, 0x66,
                     0x01, 0x00];
        let result = decode_hci_event(data).unwrap();
        assert_eq!(result.event_code, 0x03);
        assert_eq!(result.params["handle"], 0x000B);
        assert_eq!(result.params["bd_addr"], "66:55:44:33:22:11");
    }

    #[test]
    fn test_decode_le_meta_event_connection_complete() {
        // LE Meta Event, subevent=0x01 (LE Connection Complete)
        let data = &[0x3E, 0x13, 0x01, 0x00, 0x40, 0x00,
                     0x01, 0x01, 0x22, 0x33, 0x44, 0x55, 0x66,
                     0x24, 0x00, 0x00, 0x00, 0x00, 0x00,
                     0x2A, 0x00];
        let result = decode_hci_event(data).unwrap();
        assert_eq!(result.subevent, Some(0x01));
    }

    #[test]
    fn test_decode_hci_acl_data() {
        // ACL: handle=0x000B, PB=2(first auto flush), BC=0, len=8
        let data = &[0x0B, 0x20, 0x08, 0x00,
                     0x04, 0x00, 0x04, 0x00, 0x02, 0x01, 0x04, 0x00];
        let result = decode_hci_acl(data).unwrap();
        assert_eq!(result.handle, 0x000B);
        assert_eq!(result.pb_flag, 2);
        assert_eq!(result.data_length, 8);
    }

    // ===== 边界用例 =====

    #[test]
    fn test_decode_hci_command_truncated() {
        // 只有 1 字节，不够解析 opcode
        let data = &[0x03];
        let result = decode_hci_command(data);
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), DecodeError::Truncated { .. }));
    }

    #[test]
    fn test_decode_hci_event_zero_length() {
        // Event with parameter length = 0
        let data = &[0xFF, 0x00];
        let result = decode_hci_event(data).unwrap();
        assert_eq!(result.event_code, 0xFF);
        assert_eq!(result.params.len(), 0);
    }

    #[test]
    fn test_decode_hci_command_parameter_length_exceeds_data() {
        // 声称参数长度为 10，实际只有 2 字节
        let data = &[0x03, 0x0C, 0x0A, 0x01, 0x02];
        let result = decode_hci_command(data).unwrap();
        assert!(!result.errors.is_empty()); // 有 warning 但不 panic
    }

    #[test]
    fn test_decode_unknown_opcode() {
        // 未知的 OGF/OCF 组合
        let data = &[0xFF, 0xFF, 0x00];
        let result = decode_hci_command(data).unwrap();
        assert_eq!(result.summary, "Unknown Command (OGF=0x3F, OCF=0x03FF)");
    }

    #[test]
    fn test_decode_unknown_event_code() {
        let data = &[0xFE, 0x01, 0x00];
        let result = decode_hci_event(data).unwrap();
        assert!(result.summary.contains("Unknown Event"));
    }
}
```

#### 3.1.2 L2CAP 解码器测试用例

```rust
#[cfg(test)]
mod l2cap_tests {
    #[test]
    fn test_decode_l2cap_signaling_connection_request() {
        // L2CAP Connection Request: PSM=0x0019(AVDTP), SCID=0x0041
        let data = &[0x08, 0x00, 0x01, 0x00,  // L2CAP header: len=8, CID=0x0001
                     0x02, 0x01, 0x04, 0x00,   // Code=0x02, ID=1, Len=4
                     0x19, 0x00, 0x41, 0x00];  // PSM=0x0019, SCID=0x0041
        let result = decode_l2cap(data).unwrap();
        assert_eq!(result.cid, 0x0001);
        assert_eq!(result.signaling.code, 0x02);
        assert_eq!(result.signaling.psm, 0x0019);
    }

    #[test]
    fn test_decode_l2cap_att_channel() {
        // CID=0x0004 (ATT)
        let data = &[0x03, 0x00, 0x04, 0x00,  // len=3, CID=0x0004
                     0x02, 0x17, 0x00];        // ATT Exchange MTU Request, MTU=23
        let result = decode_l2cap(data).unwrap();
        assert_eq!(result.cid, 0x0004);
        assert_eq!(result.protocol, "ATT");
    }

    #[test]
    fn test_decode_l2cap_smp_channel() {
        // CID=0x0006 (SMP)
        let data = &[0x07, 0x00, 0x06, 0x00,  // len=7, CID=0x0006
                     0x01, 0x04, 0x00, 0x0D, 0x10, 0x0B, 0x0B];
        let result = decode_l2cap(data).unwrap();
        assert_eq!(result.cid, 0x0006);
        assert_eq!(result.protocol, "SMP");
    }

    #[test]
    fn test_decode_l2cap_length_mismatch() {
        // 声称 length=100 但实际数据不足
        let data = &[0x64, 0x00, 0x04, 0x00, 0x01, 0x02];
        let result = decode_l2cap(data).unwrap();
        assert!(!result.errors.is_empty());
    }

    #[test]
    fn test_decode_l2cap_dynamic_cid() {
        // CID=0x0040 (动态分配)，需要上下文确定协议
        let data = &[0x04, 0x00, 0x40, 0x00, 0x01, 0x02, 0x03, 0x04];
        let ctx = ConnectionContext::with_channel(0x0040, "AVDTP");
        let result = decode_l2cap_with_context(data, &ctx).unwrap();
        assert_eq!(result.protocol, "AVDTP");
    }
}
```

#### 3.1.3 ATT 解码器测试用例

```rust
#[cfg(test)]
mod att_tests {
    #[test]
    fn test_decode_att_exchange_mtu_request() {
        let data = &[0x02, 0x00, 0x02]; // opcode=0x02, MTU=512
        let result = decode_att(data).unwrap();
        assert_eq!(result.opcode, 0x02);
        assert_eq!(result.summary, "Exchange MTU Request MTU=512");
    }

    #[test]
    fn test_decode_att_write_request() {
        let data = &[0x12, 0x25, 0x00, 0x01, 0x00]; // handle=0x0025, value=0x0001
        let result = decode_att(data).unwrap();
        assert_eq!(result.opcode, 0x12);
        assert_eq!(result.handle, 0x0025);
    }

    #[test]
    fn test_decode_att_notification() {
        let data = &[0x1B, 0x19, 0x00, 0x64]; // handle=0x0019, value=100
        let result = decode_att(data).unwrap();
        assert_eq!(result.opcode, 0x1B);
        assert_eq!(result.summary, "Notification Handle=0x0019");
    }

    #[test]
    fn test_decode_att_error_response() {
        // Error: req=0x0A(Read), handle=0x0001, error=0x05(Authentication)
        let data = &[0x01, 0x0A, 0x01, 0x00, 0x05];
        let result = decode_att(data).unwrap();
        assert_eq!(result.error_code, Some(0x05));
        assert!(result.summary.contains("Authentication Insufficient"));
    }

    #[test]
    fn test_decode_att_read_by_group_type_response() {
        // 服务发现响应
        let data = &[0x11, 0x06,
                     0x01, 0x00, 0x05, 0x00, 0x00, 0x18,  // handle 1-5, UUID=0x1800
                     0x06, 0x00, 0x09, 0x00, 0x01, 0x18]; // handle 6-9, UUID=0x1801
        let result = decode_att(data).unwrap();
        assert_eq!(result.services.len(), 2);
    }

    #[test]
    fn test_decode_att_unknown_opcode() {
        let data = &[0xFF, 0x01, 0x02];
        let result = decode_att(data).unwrap();
        assert!(result.summary.contains("Unknown"));
    }
}
```

#### 3.1.4 SMP 解码器测试用例

```rust
#[cfg(test)]
mod smp_tests {
    #[test]
    fn test_decode_smp_pairing_request() {
        // IO=DisplayYesNo, OOB=0, AuthReq=0x0D, MaxKeySize=16
        let data = &[0x01, 0x01, 0x00, 0x0D, 0x10, 0x0B, 0x0B];
        let result = decode_smp(data).unwrap();
        assert_eq!(result.code, 0x01);
        assert_eq!(result.io_capability, "DisplayYesNo");
        assert_eq!(result.max_key_size, 16);
    }

    #[test]
    fn test_decode_smp_pairing_failed() {
        let data = &[0x05, 0x04]; // Reason=0x04 (Confirm Value Failed)
        let result = decode_smp(data).unwrap();
        assert!(result.summary.contains("Confirm Value Failed"));
    }

    #[test]
    fn test_decode_smp_public_key() {
        let data = vec![0x0C];
        data.extend_from_slice(&[0xAA; 32]); // X coordinate
        data.extend_from_slice(&[0xBB; 32]); // Y coordinate
        let result = decode_smp(&data).unwrap();
        assert_eq!(result.code, 0x0C);
        assert_eq!(result.fields.len(), 2); // X and Y
    }
}
```

#### 3.1.5 AVDTP 解码器测试用例

```rust
#[cfg(test)]
mod avdtp_tests {
    #[test]
    fn test_decode_avdtp_discover_command() {
        let data = &[0x00, 0x01]; // Transaction=0, Type=Command, Signal=DISCOVER
        let result = decode_avdtp(data).unwrap();
        assert_eq!(result.signal_id, 0x01);
        assert_eq!(result.msg_type, "Command");
        assert_eq!(result.summary, "DISCOVER");
    }

    #[test]
    fn test_decode_avdtp_set_configuration() {
        // SET_CONFIGURATION with SBC codec info
        let data = &[0x20, 0x03,  // Transaction=1, Command, SET_CONFIG
                     0x04,        // ACP SEID=1
                     0x04,        // INT SEID=1
                     0x07, 0x06, 0x00, 0x00, 0xFF, 0xFF, 0x02, 0x35]; // Media Codec SBC
        let result = decode_avdtp(data).unwrap();
        assert_eq!(result.signal_id, 0x03);
        assert!(result.summary.contains("SBC"));
    }
}
```

### 3.2 过滤引擎测试用例

```rust
#[cfg(test)]
mod filter_tests {
    // ===== 语法解析测试 =====

    #[test]
    fn test_parse_simple_comparison() {
        let filter = compile("hci.type == command").unwrap();
        // 验证 AST 结构正确
    }

    #[test]
    fn test_parse_and_expression() {
        let filter = compile("hci.type == acl && l2cap.cid == 0x0004").unwrap();
    }

    #[test]
    fn test_parse_or_expression() {
        let filter = compile("att.opcode == 0x12 || att.opcode == 0x52").unwrap();
    }

    #[test]
    fn test_parse_not_expression() {
        let filter = compile("!(hci.type == event)").unwrap();
    }

    #[test]
    fn test_parse_nested_parentheses() {
        let filter = compile("(a == 1 || b == 2) && (c == 3)").unwrap();
    }

    #[test]
    fn test_parse_contains() {
        let filter = compile("contains \"Reset\"").unwrap();
    }

    #[test]
    fn test_parse_hex_value() {
        let filter = compile("hci.opcode == 0x0C03").unwrap();
    }

    #[test]
    fn test_parse_invalid_syntax() {
        let result = compile("hci.type ==");
        assert!(result.is_err());
    }

    #[test]
    fn test_parse_unknown_field() {
        let result = compile("hci.unknown == 1");
        assert!(result.is_err());
    }

    #[test]
    fn test_parse_max_nesting_depth() {
        // 超过 16 层嵌套应报错
        let expr = "(".repeat(20) + "a == 1" + &")".repeat(20);
        let result = compile(&expr);
        assert!(result.is_err());
    }

    // ===== 过滤执行测试 =====

    #[test]
    fn test_filter_by_hci_type() {
        let filter = compile("hci.type == command").unwrap();
        let cmd_packet = make_hci_command_packet();
        let evt_packet = make_hci_event_packet();
        assert!(filter(&cmd_packet));
        assert!(!filter(&evt_packet));
    }

    #[test]
    fn test_filter_by_direction() {
        let filter = compile("direction == sent").unwrap();
        let sent = make_packet(Direction::Sent);
        let recv = make_packet(Direction::Received);
        assert!(filter(&sent));
        assert!(!filter(&recv));
    }

    #[test]
    fn test_filter_combined_and() {
        let filter = compile("hci.type == acl && direction == sent").unwrap();
        let match_pkt = make_acl_sent_packet();
        let nomatch = make_acl_received_packet();
        assert!(filter(&match_pkt));
        assert!(!filter(&nomatch));
    }

    #[test]
    fn test_filter_field_not_present() {
        // ATT 字段对非 ATT 包应返回 false
        let filter = compile("att.opcode == 0x12").unwrap();
        let hci_cmd = make_hci_command_packet();
        assert!(!filter(&hci_cmd));
    }

    #[test]
    fn test_filter_contains_text() {
        let filter = compile("contains \"Reset\"").unwrap();
        let reset_pkt = make_packet_with_summary("HCI Command: HCI_Reset");
        let other_pkt = make_packet_with_summary("HCI Event: Inquiry Complete");
        assert!(filter(&reset_pkt));
        assert!(!filter(&other_pkt));
    }
}
```

### 3.3 btsnoop 解析器测试

```rust
#[cfg(test)]
mod parser_tests {
    #[test]
    fn test_parse_valid_file_header() {
        let header = b"btsnoop\x00\x00\x00\x00\x01\x00\x00\x03\xEA";
        let result = parse_file_header(header).unwrap();
        assert_eq!(result.version, 1);
        assert_eq!(result.datalink_type, 1002); // HCI UART (H4)
    }

    #[test]
    fn test_parse_invalid_magic() {
        let header = b"invalid\x00\x00\x00\x00\x01\x00\x00\x03\xEA";
        let result = parse_file_header(header);
        assert!(matches!(result, Err(ParseError::InvalidMagic)));
    }

    #[test]
    fn test_parse_packet_record() {
        // 构造一个完整的 packet record
        let record = build_test_record(/*original_len=*/3, /*included_len=*/3,
                                        /*flags=*/0, /*drops=*/0,
                                        /*timestamp=*/0x00E03AB44A676000u64,
                                        /*data=*/&[0x03, 0x0C, 0x00]);
        let result = parse_packet_record(&record).unwrap();
        assert_eq!(result.original_length, 3);
        assert_eq!(result.included_length, 3);
        assert_eq!(result.data, &[0x03, 0x0C, 0x00]);
    }

    #[test]
    fn test_parse_timestamp_conversion() {
        // btsnoop epoch: 2000-01-01 00:00:00
        let btsnoop_ts: i64 = 0x00E03AB44A676000;
        let unix_ts = btsnoop_to_unix_timestamp(btsnoop_ts);
        // Should be 2024-01-01 00:00:00 UTC (approximately)
        assert!(unix_ts > 0);
    }

    #[test]
    fn test_parse_direction_from_flags() {
        assert_eq!(direction_from_flags(0b00), Direction::Sent);
        assert_eq!(direction_from_flags(0b01), Direction::Received);
    }

    #[test]
    fn test_parse_type_from_flags() {
        assert_eq!(type_from_flags(0b00), PacketCategory::Data);
        assert_eq!(type_from_flags(0b10), PacketCategory::CommandEvent);
    }

    #[test]
    fn test_parse_streaming_partial_record() {
        // 模拟流式解析：先给一半数据，再补齐
        let mut parser = StreamingParser::new();
        let full_record = build_test_record(3, 3, 0, 0, 0, &[0x03, 0x0C, 0x00]);

        let result1 = parser.feed(&full_record[..12]); // 只给 header 部分
        assert_eq!(result1.packets.len(), 0); // 不够一个完整包

        let result2 = parser.feed(&full_record[12..]); // 补齐剩余
        assert_eq!(result2.packets.len(), 1);
    }

    #[test]
    fn test_parse_multiple_records() {
        let data = build_test_file_with_n_packets(100);
        let result = parse_btsnoop(&data).unwrap();
        assert_eq!(result.packets.len(), 100);
    }

    #[test]
    fn test_parse_empty_file_after_header() {
        let data = b"btsnoop\x00\x00\x00\x00\x01\x00\x00\x03\xEA";
        let result = parse_btsnoop(data).unwrap();
        assert_eq!(result.packets.len(), 0);
    }

    #[test]
    fn test_parse_truncated_record() {
        // 文件在某个 record 中间截断
        let data = build_test_file_with_truncated_last_record();
        let result = parse_btsnoop(&data).unwrap();
        assert!(!result.warnings.is_empty());
        // 前面完整的包仍然可用
        assert!(result.packets.len() > 0);
    }
}
```

### 3.4 API 集成测试

```rust
#[cfg(test)]
mod api_tests {
    use axum_test::TestServer;

    #[tokio::test]
    async fn test_create_session() {
        let server = spawn_test_server().await;
        let resp = server.post("/api/v1/session")
            .json(&json!({"mode": "file"}))
            .await;
        assert_eq!(resp.status(), 200);
        let body: Value = resp.json();
        assert!(body["session_id"].is_string());
        assert!(body["ws_url"].as_str().unwrap().contains("/ws/session/"));
    }

    #[tokio::test]
    async fn test_upload_and_query_packets() {
        let server = spawn_test_server().await;

        // 1. 创建会话
        let session = create_session(&server, "file").await;

        // 2. 上传文件
        let btsnoop_data = include_bytes!("../testdata/sample.btsnoop");
        let resp = server.post(&format!("/api/v1/session/{}/upload", session.id))
            .multipart(form().file("file", btsnoop_data))
            .await;
        assert_eq!(resp.status(), 200);

        // 3. 查询包列表
        let resp = server.get(&format!("/api/v1/session/{}/packets?limit=10", session.id))
            .await;
        assert_eq!(resp.status(), 200);
        let body: Value = resp.json();
        assert!(body["total"].as_u64().unwrap() > 0);
        assert!(body["packets"].as_array().unwrap().len() <= 10);
    }

    #[tokio::test]
    async fn test_get_packet_detail() {
        let server = spawn_test_server().await;
        let session = create_and_upload_session(&server).await;

        let resp = server.get(&format!("/api/v1/session/{}/packets/0", session.id))
            .await;
        assert_eq!(resp.status(), 200);
        let body: Value = resp.json();
        assert!(body["layers"].as_array().unwrap().len() > 0);
        assert!(body["raw_hex"].is_string());
    }

    #[tokio::test]
    async fn test_filter_packets() {
        let server = spawn_test_server().await;
        let session = create_and_upload_session(&server).await;

        let resp = server.get(&format!(
            "/api/v1/session/{}/packets?filter=hci.type==command", session.id))
            .await;
        assert_eq!(resp.status(), 200);
        let body: Value = resp.json();
        assert!(body["filtered_total"].as_u64().unwrap() < body["total"].as_u64().unwrap());
    }

    #[tokio::test]
    async fn test_invalid_filter_returns_400() {
        let server = spawn_test_server().await;
        let session = create_and_upload_session(&server).await;

        let resp = server.get(&format!(
            "/api/v1/session/{}/packets?filter=invalid syntax!!!", session.id))
            .await;
        assert_eq!(resp.status(), 400);
    }

    #[tokio::test]
    async fn test_session_not_found() {
        let server = spawn_test_server().await;
        let resp = server.get("/api/v1/session/nonexistent-uuid/packets").await;
        assert_eq!(resp.status(), 404);
    }

    #[tokio::test]
    async fn test_session_stats() {
        let server = spawn_test_server().await;
        let session = create_and_upload_session(&server).await;

        let resp = server.get(&format!("/api/v1/session/{}/stats", session.id)).await;
        assert_eq!(resp.status(), 200);
        let body: Value = resp.json();
        assert!(body["total_packets"].as_u64().unwrap() > 0);
        assert!(body["breakdown"]["by_type"].is_object());
    }

    #[tokio::test]
    async fn test_file_too_large() {
        let server = spawn_test_server_with_config(Config { max_file_size: 1024 }).await;
        let session = create_session(&server, "file").await;

        let large_data = vec![0u8; 2048];
        let resp = server.post(&format!("/api/v1/session/{}/upload", session.id))
            .multipart(form().file("file", &large_data))
            .await;
        assert_eq!(resp.status(), 413);
    }

    #[tokio::test]
    async fn test_invalid_btsnoop_format() {
        let server = spawn_test_server().await;
        let session = create_session(&server, "file").await;

        let invalid_data = b"this is not a btsnoop file";
        let resp = server.post(&format!("/api/v1/session/{}/upload", session.id))
            .multipart(form().file("file", invalid_data))
            .await;
        assert_eq!(resp.status(), 400);
    }
}
```

### 3.5 WebSocket 集成测试

```rust
#[cfg(test)]
mod ws_tests {
    #[tokio::test]
    async fn test_ws_connect_and_receive_packets() {
        let server = spawn_test_server().await;
        let session = create_session(&server, "file").await;

        // 连接 WebSocket
        let mut ws = connect_ws(&format!("/ws/session/{}", session.id)).await;

        // 上传文件触发推送
        upload_file(&server, &session.id, include_bytes!("../testdata/sample.btsnoop")).await;

        // 应收到 packet_batch 消息
        let msg = ws.recv_timeout(Duration::from_secs(5)).await.unwrap();
        let data: Value = serde_json::from_str(&msg).unwrap();
        assert_eq!(data["type"], "packet_batch");
        assert!(data["packets"].as_array().unwrap().len() > 0);
    }

    #[tokio::test]
    async fn test_ws_set_filter() {
        let server = spawn_test_server().await;
        let session = create_and_upload_session(&server).await;

        let mut ws = connect_ws(&format!("/ws/session/{}", session.id)).await;

        // 发送过滤命令
        ws.send(json!({"type": "set_filter", "expression": "hci.type == command"})).await;

        // 应收到过滤后的包批次
        let msg = ws.recv_timeout(Duration::from_secs(5)).await.unwrap();
        let data: Value = serde_json::from_str(&msg).unwrap();
        assert_eq!(data["type"], "packet_batch");
    }

    #[tokio::test]
    async fn test_ws_get_detail() {
        let server = spawn_test_server().await;
        let session = create_and_upload_session(&server).await;

        let mut ws = connect_ws(&format!("/ws/session/{}", session.id)).await;
        ws.send(json!({"type": "get_detail", "index": 0})).await;

        let msg = ws.recv_timeout(Duration::from_secs(5)).await.unwrap();
        let data: Value = serde_json::from_str(&msg).unwrap();
        assert_eq!(data["type"], "packet_detail");
        assert!(data["data"]["layers"].is_array());
    }
}
```

## 4. 前端测试规范

### 4.1 组件测试 (Vitest + Testing Library)

```typescript
// PacketList.test.tsx
describe('PacketList', () => {
  it('renders packet summaries correctly', () => {
    const packets = [mockPacketSummary({ index: 0, summary: 'HCI_Reset' })];
    render(<PacketList packets={packets} />);
    expect(screen.getByText('HCI_Reset')).toBeInTheDocument();
  });

  it('highlights selected row', () => {
    const packets = [mockPacketSummary({ index: 0 })];
    render(<PacketList packets={packets} selectedIndex={0} />);
    expect(screen.getByRole('row')).toHaveClass('selected');
  });

  it('calls onClick when row is clicked', () => {
    const onClick = vi.fn();
    const packets = [mockPacketSummary({ index: 5 })];
    render(<PacketList packets={packets} onSelect={onClick} />);
    fireEvent.click(screen.getByRole('row'));
    expect(onClick).toHaveBeenCalledWith(5);
  });

  it('renders empty state when no packets', () => {
    render(<PacketList packets={[]} />);
    expect(screen.getByText(/no packets/i)).toBeInTheDocument();
  });

  it('displays direction arrows correctly', () => {
    const packets = [
      mockPacketSummary({ direction: 'sent' }),
      mockPacketSummary({ direction: 'received' }),
    ];
    render(<PacketList packets={packets} />);
    expect(screen.getByText('→')).toBeInTheDocument();
    expect(screen.getByText('←')).toBeInTheDocument();
  });
});

// FilterBar.test.tsx
describe('FilterBar', () => {
  it('applies filter on Enter', () => {
    const onFilter = vi.fn();
    render(<FilterBar onFilter={onFilter} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'hci.type == command' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onFilter).toHaveBeenCalledWith('hci.type == command');
  });

  it('shows error state for invalid filter', () => {
    render(<FilterBar error="Syntax error at position 5" />);
    expect(screen.getByText(/syntax error/i)).toBeInTheDocument();
  });

  it('clears filter on Escape', () => {
    const onFilter = vi.fn();
    render(<FilterBar onFilter={onFilter} currentFilter="hci.type == command" />);
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Escape' });
    expect(onFilter).toHaveBeenCalledWith('');
  });
});

// HexView.test.tsx
describe('HexView', () => {
  it('renders hex bytes with correct formatting', () => {
    const data = new Uint8Array([0x04, 0x0e, 0x04, 0x01]);
    render(<HexView data={data} />);
    expect(screen.getByText('04 0e 04 01')).toBeInTheDocument();
  });

  it('highlights bytes when selection is provided', () => {
    const data = new Uint8Array([0x04, 0x0e, 0x04, 0x01]);
    render(<HexView data={data} highlight={{ offset: 1, length: 2 }} />);
    // bytes at offset 1-2 should have highlight class
  });

  it('shows ASCII representation', () => {
    const data = new Uint8Array([0x48, 0x65, 0x6C, 0x6C, 0x6F]); // "Hello"
    render(<HexView data={data} />);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });
});
```

### 4.2 WebSocket Hook 测试

```typescript
// useWebSocket.test.ts
describe('useWebSocket', () => {
  it('connects to session ws url', async () => {
    const { result } = renderHook(() => useWebSocket('session-123'));
    await waitFor(() => expect(result.current.status).toBe('connected'));
  });

  it('receives and parses packet batch', async () => {
    const { result } = renderHook(() => useWebSocket('session-123'));
    mockWsServer.send(JSON.stringify({
      type: 'packet_batch',
      packets: [{ index: 0, summary: 'test' }],
    }));
    await waitFor(() => expect(result.current.packets).toHaveLength(1));
  });

  it('reconnects on disconnect', async () => {
    const { result } = renderHook(() => useWebSocket('session-123'));
    mockWsServer.close();
    await waitFor(() => expect(result.current.status).toBe('reconnecting'));
  });
});
```

## 5. 性能测试

### 5.1 Benchmark 用例

```rust
// benches/decode_benchmark.rs
use criterion::{criterion_group, criterion_main, Criterion};

fn bench_parse_btsnoop_1mb(c: &mut Criterion) {
    let data = include_bytes!("../testdata/1mb_sample.btsnoop");
    c.bench_function("parse_1mb_btsnoop", |b| {
        b.iter(|| parse_btsnoop(data))
    });
}

fn bench_decode_hci_command(c: &mut Criterion) {
    let data = &[0x03, 0x0C, 0x00];
    c.bench_function("decode_hci_command", |b| {
        b.iter(|| decode_hci_command(data))
    });
}

fn bench_decode_full_stack(c: &mut Criterion) {
    // ATT Write Request inside L2CAP inside HCI ACL
    let data = build_full_stack_packet();
    c.bench_function("decode_full_stack", |b| {
        b.iter(|| decode_packet(&data))
    });
}

fn bench_filter_100k_packets(c: &mut Criterion) {
    let packets = generate_test_packets(100_000);
    let filter = compile("hci.type == acl && l2cap.cid == 0x0004").unwrap();
    c.bench_function("filter_100k_packets", |b| {
        b.iter(|| packets.iter().filter(|p| filter(p)).count())
    });
}

criterion_group!(benches,
    bench_parse_btsnoop_1mb,
    bench_decode_hci_command,
    bench_decode_full_stack,
    bench_filter_100k_packets
);
criterion_main!(benches);
```

### 5.2 性能基线

| 测试项                | 基线目标       | 回归阈值 (触发告警) |
|----------------------|---------------|---------------------|
| parse_1mb_btsnoop    | < 10ms        | > 15ms (+50%)       |
| decode_hci_command   | < 100ns       | > 200ns             |
| decode_full_stack    | < 1μs         | > 2μs               |
| filter_100k_packets  | < 50ms        | > 100ms             |

## 6. 测试数据管理

### 6.1 测试数据目录结构

```
testdata/
├── sample.btsnoop              # 基础测试文件 (~10KB, 约100个包)
├── 1mb_sample.btsnoop          # 性能测试文件
├── hci_only.btsnoop            # 仅 HCI Command/Event
├── ble_gatt.btsnoop            # BLE GATT 交互
├── a2dp_streaming.btsnoop      # A2DP 音频流
├── pairing_flow.btsnoop        # 完整配对流程
├── truncated.btsnoop           # 截断文件（测试容错）
├── empty_after_header.btsnoop  # 空文件（只有 header）
├── invalid_magic.bin           # 非法 magic（测试拒绝）
├── large_packet.btsnoop        # 含超大包（测试边界）
└── wireshark_reference/        # Wireshark 导出的对比基准
    ├── sample_decoded.json
    └── ble_gatt_decoded.json
```

### 6.2 对比验证

使用 Wireshark `tshark` 导出的解码结果作为 ground truth：

```bash
# 生成参考数据
tshark -r sample.btsnoop -T json > wireshark_reference/sample_decoded.json
```

对比测试确保我们的解码结果与 Wireshark 一致（字段名可不同，值必须一致）。

## 7. 测试覆盖率要求

| 模块           | 行覆盖率要求 | 分支覆盖率要求 |
|----------------|-------------|---------------|
| 解码器 (各协议) | ≥ 90%       | ≥ 80%        |
| 过滤引擎       | ≥ 95%       | ≥ 90%        |
| btsnoop 解析器 | ≥ 95%       | ≥ 90%        |
| API handler    | ≥ 85%       | ≥ 75%        |
| 前端组件       | ≥ 80%       | -            |

使用工具：
- 后端：`cargo-tarpaulin` 或 `llvm-cov`
- 前端：`vitest --coverage`
