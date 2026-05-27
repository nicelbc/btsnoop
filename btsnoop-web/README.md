# btsnoop-web

基于 Web 的蓝牙 btsnoop 实时解析工具，Wireshark 风格的三面板 UI。

## 功能

- 拖拽上传 btsnoop 文件，浏览器内实时解析
- HCI / L2CAP / AVDTP / AVRCP / ATT / SMP 逐层协议解码
- Wireshark 风格显示过滤（支持 `hci.type == command && direction == sent`）
- 虚拟滚动支持 10 万+ 数据包
- HexView 字节高亮联动
- A2DP Codec 参数解析（SBC/AAC/LDAC/LHDC/aptX）

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
python server.py
# 默认监听 http://localhost:8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 默认 http://localhost:5173，自动代理到后端
```

## 技术栈

- **后端**: Python + FastAPI + WebSocket
- **前端**: React + TypeScript + Vite + TailwindCSS + @tanstack/react-virtual
- **协议解析**: 纯 Python 实现，覆盖蓝牙 HCI/L2CAP/AVDTP/AVRCP/ATT/SMP

## 项目结构

```
btsnoop-web/
├── backend/
│   ├── parser/          # 协议解析核心
│   │   ├── btsnoop.py   # btsnoop 文件格式
│   │   ├── hci.py       # HCI 层
│   │   ├── l2cap.py     # L2CAP 层
│   │   ├── avdtp.py     # AVDTP/A2DP
│   │   ├── avrcp.py     # AVCTP/AVRCP
│   │   ├── att.py       # ATT/GATT (BLE)
│   │   └── smp.py       # SMP 配对
│   ├── server.py        # FastAPI 主服务
│   ├── session.py       # 会话管理
│   └── filter_engine.py # 过滤表达式引擎
├── frontend/
│   └── src/
│       ├── components/  # React 组件
│       ├── stores/      # 全局状态
│       └── ws/          # WebSocket 客户端
└── README.md
```
