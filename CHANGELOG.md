# Changelog

## v1.0.0 (2026-05-27)

### 功能
- **Web 平台**: 浏览器内 Wireshark 风格 btsnoop 解析
  - 拖拽上传文件，实时解析显示
  - 三面板布局: PacketList + ProtocolTree + HexView
  - 虚拟滚动支持 10 万+ 数据包
  - Wireshark 风格显示过滤引擎
  - 右键菜单快速过滤
  - 统计面板（协议分布、方向、速率）
  - 导出: pcapng (Wireshark 兼容) / JSON / CSV

- **ADB 实时抓包**: 连接 Android 设备，实时流式解析
  - 增量拉取，低延迟 WebSocket 推送
  - 前端自动滚动跟随新包

- **协议解码**: 完整蓝牙协议栈覆盖
  - HCI: Command/Event/ACL/SCO/ISO
  - L2CAP: 信令解码 + CID/PSM 动态路由
  - AVDTP/A2DP: 信令 + Codec 参数 (SBC/AAC/LDAC/LHDC/aptX)
  - AVRCP: PASS THROUGH + VENDOR DEPENDENT
  - ATT/GATT: 全 opcode 支持
  - SMP: 配对流程全解码
  - RFCOMM: 帧类型/MUX/PN/MSC
  - SDP: PDU 类型/UUID/服务搜索

- **CLI 工具** (`bt-snoop-live`): 终端实时彩色解析
  - 通过 ADB 实时抓取
  - 本地文件解析
  - 协议层过滤

### 技术栈
- 后端: Python + FastAPI + WebSocket
- 前端: React + TypeScript + Vite + TailwindCSS
- 部署: Docker + docker-compose
- 测试: pytest (187) + vitest (29)
