# 用户使用手册

## 1. 快速开始

### 1.1 访问工具

浏览器打开部署地址（如 `https://btsnoop.example.com`），无需安装任何软件。

支持浏览器：Chrome 90+、Firefox 90+、Edge 90+、Safari 15+。

### 1.2 解析 btsnoop 文件

1. 打开网页，进入主界面
2. 将 btsnoop 文件拖拽到上传区域，或点击"选择文件"按钮
3. 等待解析完成（进度条会实时显示）
4. 在包列表中浏览解析结果

### 1.3 获取 btsnoop 文件

**Android 设备：**

```bash
# 方法一：开发者选项开启 HCI log
设置 → 开发者选项 → 启用蓝牙 HCI 信息收集日志

# 重启蓝牙后操作，然后导出
adb pull /data/misc/bluetooth/logs/btsnoop_hci.log

# 方法二：Bug Report 中提取
adb bugreport bugreport.zip
# 解压后在 FS/data/misc/bluetooth/logs/ 目录下
```

**Linux：**

```bash
# 使用 btmon 抓取
sudo btmon --write capture.btsnoop

# 或使用 hcidump
sudo hcidump --raw --save-dump=capture.btsnoop
```

## 2. 界面说明

### 2.1 整体布局

```
┌────────────────────────────────────────────────────┐
│  [过滤栏]   [统计]   [设置]                         │
├────────────────────────────────────────────────────┤
│                                                     │
│  数据包列表 (上半区)                                 │
│  No. | Time | Direction | Protocol | Length | Info  │
│  ─────────────────────────────────────────────────  │
│  1   | 0.000| →  Sent   | HCI CMD  | 3     | Reset │
│  2   | 0.015| ←  Recv   | HCI EVT  | 7     | ...   │
│                                                     │
├────────────────────────────────────────────────────┤
│                                                     │
│  协议解码树 (左下)         │  Hex 视图 (右下)        │
│  ▼ HCI Event               │  0000: 04 0e 04 01 03  │
│    Event Code: 0x0E         │  0005: 0c 00           │
│    Length: 4                 │                        │
│  ▼ L2CAP                    │                        │
│    ...                      │                        │
│                                                     │
└────────────────────────────────────────────────────┘
```

### 2.2 数据包列表

| 列名       | 说明                              |
|-----------|-----------------------------------|
| No.       | 包序号                            |
| Time      | 时间戳（相对/绝对可切换）         |
| Direction | 方向（→ Sent / ← Received）      |
| Protocol  | 最高层协议名称                    |
| Length    | 包长度（字节）                    |
| Info      | 单行摘要信息                      |

**操作：**
- 单击行：选中包，下方显示解码详情
- 双击行：展开/折叠多层协议视图
- 右键菜单：复制、标记、设为过滤条件

### 2.3 协议解码树

选中某个包后，下方左侧显示逐层解码结果：

- 点击展开/折叠各协议层
- 鼠标悬停字段时，右侧 Hex 视图自动高亮对应字节
- 字段值可复制

### 2.4 Hex 视图

- 左侧：十六进制字节
- 右侧：ASCII 可见字符（不可见字符显示 `.`）
- 选中协议树字段时自动高亮对应区域
- 支持手动选择字节区域查看偏移/长度

## 3. 过滤功能

### 3.1 过滤语法

在顶部过滤栏输入表达式，回车应用。支持以下语法：

**基础比较：**

```
hci.type == command          # HCI 包类型
hci.type == event
hci.type == acl
hci.opcode == 0x0406         # HCI OpCode
hci.event == 0x0E            # 事件码
hci.handle == 0x0001         # 连接句柄
```

**L2CAP 过滤：**

```
l2cap.cid == 0x0004          # Channel ID
l2cap.psm == 0x0019          # PSM (AVDTP)
l2cap.length > 100           # 长度条件
```

**ATT/GATT 过滤：**

```
att.opcode == 0x12           # Write Request
att.opcode == write_req      # 同上（支持名称）
att.handle == 0x0025         # Attribute Handle
att.error == 0x0E            # Error Code
```

**方向和地址：**

```
direction == sent
direction == received
bt.addr == "AA:BB:CC:DD:EE:FF"
```

**逻辑组合：**

```
hci.type == acl && l2cap.psm == 0x0019
att.opcode == write_req || att.opcode == write_cmd
!(hci.type == event)
```

**文本搜索：**

```
contains "GATT"
summary contains "Reset"
```

### 3.2 快捷过滤

右键包列表中的行，可快速创建过滤条件：
- "过滤：仅此协议"
- "过滤：仅此连接"
- "过滤：仅此方向"
- "排除此协议"

### 3.3 过滤历史

过滤栏下拉可查看最近使用的过滤表达式（本地存储，最多 20 条）。

## 4. 实时模式

### 4.1 通过 ADB 实时抓包

1. 在页面上选择"实时模式"
2. 在 PC 端运行代理工具：

```bash
# 安装代理工具
npm install -g btsnoop-proxy

# 启动（自动连接 ADB 设备）
btsnoop-proxy --server ws://btsnoop.example.com/ws/live --device auto
```

3. 页面自动显示实时到达的蓝牙包

### 4.2 实时模式控制

- **暂停/恢复**：点击暂停按钮，停止自动滚动但继续接收数据
- **清空**：清除当前会话所有数据，重新开始
- **导出**：将已收集的数据导出为文件

## 5. 导出功能

### 5.1 支持的导出格式

| 格式    | 说明                          | 用途                |
|---------|-------------------------------|---------------------|
| JSON    | 完整解码结果                  | 程序化处理          |
| CSV     | 摘要信息表格                  | Excel 分析          |
| pcapng  | 标准抓包格式                  | Wireshark 打开      |
| Text    | 人类可读的纯文本              | 报告/邮件           |

### 5.2 导出选项

- 全部导出 / 仅导出过滤后的包
- 选择包含的字段
- 时间格式选择（绝对/相对）

## 6. 常见使用场景

### 6.1 蓝牙连接问题排查

推荐过滤：
```
hci.type == event && (hci.event == 0x03 || hci.event == 0x05)
```
查看所有连接建立和断开事件，关注 Status 和 Reason 字段。

### 6.2 BLE GATT 通信调试

推荐过滤：
```
l2cap.cid == 0x0004
```
查看所有 ATT 层交互，包括服务发现、读写特征值、通知等。

### 6.3 A2DP 音频流分析

推荐过滤：
```
l2cap.psm == 0x0019
```
查看 AVDTP 信令（能力协商、编码器配置、启动/暂停）。

### 6.4 配对过程分析

推荐过滤：
```
l2cap.cid == 0x0006
```
查看 SMP 配对流程（配对请求、密钥交换、加密建立）。

## 7. 键盘快捷键

| 快捷键       | 功能                    |
|--------------|-------------------------|
| Ctrl+F       | 聚焦过滤栏              |
| Ctrl+G       | 跳转到指定包序号        |
| ↑ / ↓       | 上下选择包              |
| Enter        | 展开/折叠选中包详情     |
| Ctrl+C       | 复制选中字段值          |
| Ctrl+E       | 导出                    |
| Space        | 暂停/恢复自动滚动      |
| Escape       | 清除过滤/取消选择       |
| Ctrl+D       | 切换暗色/亮色主题       |

## 8. 设置选项

### 8.1 显示设置

- 时间格式：绝对时间 / 相对时间 / 两者都显示
- 主题：亮色 / 暗色 / 跟随系统
- 字体大小：12px ~ 18px
- Hex 视图：显示/隐藏 ASCII 区域

### 8.2 解码设置

- 自动解码层级：全部 / 仅到 L2CAP / 仅 HCI
- 显示原始字节：开/关
- UUID 显示：数字 / 名称 / 两者

### 8.3 性能设置

- 最大内存包数（超过后丢弃最早的包）
- 自动滚动缓冲区大小
- 批量加载数量
