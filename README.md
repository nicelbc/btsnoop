# btsnoop

蓝牙 HCI btsnoop 解析工具集，包含终端实时抓包工具和 Web 在线解析平台。

## 工具列表

### bt-snoop-live（终端工具）

实时读取手机 btsnoop_hci.log，Wireshark 风格终端彩色解析显示。

```bash
./bt-snoop-live                      # 实时抓取（通过 adb）
./bt-snoop-live -f file.cfa          # 解析本地 btsnoop 文件
./bt-snoop-live --filter avdtp       # 只看 AVDTP
./bt-snoop-live --filter hci,l2cap   # 多协议过滤
```

支持协议：HCI CMD/EVT、ACL、L2CAP、AVDTP/A2DP、AVRCP、SDP、ATT/GATT

### btsnoop-web（Web 平台）

浏览器内 Wireshark 风格的 btsnoop 解析工具，拖入文件即可查看。

```bash
# 启动后端
cd btsnoop-web/backend
pip install -r requirements.txt
python server.py

# 启动前端
cd btsnoop-web/frontend
npm install
npm run dev
```

功能：
- 拖拽上传 btsnoop/cfa 文件
- HCI / L2CAP / AVDTP / AVRCP / ATT / SMP 逐层协议解码
- Wireshark 风格显示过滤
- 虚拟滚动支持 10 万+ 数据包
- HexView 字节高亮联动
- A2DP Codec 参数解析（SBC/AAC/LDAC/LHDC/aptX）

## 协议覆盖

| 层级 | 协议 |
|------|------|
| HCI | Command, Event, ACL, SCO, ISO |
| L2CAP | Signaling, CID/PSM routing |
| 上层 | AVDTP, AVRCP, SDP, RFCOMM, ATT/GATT, SMP |
| Codec | SBC, AAC, LDAC, LHDC 2.0/3.0/4.0/V5, aptX/HD/Adaptive |

## 测试

```bash
cd btsnoop-web/backend
python -m pytest tests/ -v
```

## License

MIT
