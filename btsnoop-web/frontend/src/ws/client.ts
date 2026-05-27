import { WsMessage, WsCommand } from '../types';
import { PacketAction } from '../stores/packetStore';

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private dispatch: React.Dispatch<PacketAction>;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private sessionId: string;
  private filterPending = false;
  private filterVersion = 0;
  private activeFilterVersion = 0;
  private wsPath: string;

  constructor(sessionId: string, dispatch: React.Dispatch<PacketAction>, live = false) {
    this.sessionId = sessionId;
    this.dispatch = dispatch;
    this.wsPath = live ? `/ws/live/${sessionId}` : `/ws/${sessionId}`;
  }

  connect(): void {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}${this.wsPath}`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.dispatch({ type: 'SET_WS_CONNECTED', connected: true });
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        console.log('[WS] Received:', msg.type, 'packets' in msg ? (msg as any).packets?.length : '');
        this.handleMessage(msg);
      } catch (err) {
        console.error('[WS] Failed to parse message:', err);
      }
    };

    this.ws.onclose = () => {
      this.dispatch({ type: 'SET_WS_CONNECTED', connected: false });
      this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      console.error('[WS] Error:', err);
      this.ws?.close();
    };
  }

  private handleMessage(msg: WsMessage): void {
    switch (msg.type) {
      case 'packet_batch':
        if (this.filterPending) {
          // First batch after filter: replace all packets
          if (this.activeFilterVersion === this.filterVersion) {
            this.dispatch({ type: 'SET_PACKETS', packets: msg.packets });
          }
          this.filterPending = false;
        } else {
          // Only accept if this is from the current filter version
          if (this.activeFilterVersion === this.filterVersion) {
            this.dispatch({ type: 'ADD_PACKETS', packets: msg.packets });
          }
        }
        break;
      case 'packet_detail':
        this.dispatch({
          type: 'SET_DETAIL',
          detail: { packet: msg.packet, raw_hex: msg.raw_hex, flags: msg.flags },
        });
        break;
      case 'filter_applied':
        this.activeFilterVersion = this.filterVersion;
        this.filterPending = true;
        this.dispatch({ type: 'SET_PACKETS', packets: [] });
        break;
      case 'connected':
        this.dispatch({ type: 'SET_SESSION_ID', sessionId: msg.session_id });
        break;
      case 'error':
        console.error('[WS] Server error:', msg.message);
        break;
      default:
        // Handle live_stopped and other unknown messages
        if ((msg as any).type === 'live_stopped') {
          this.dispatch({ type: 'SET_WS_CONNECTED', connected: false });
        }
        break;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 3000);
  }

  send(command: WsCommand): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(command));
    }
  }

  requestDetail(index: number): void {
    this.send({ action: 'get_detail', index });
  }

  setFilter(expression: string): void {
    this.filterVersion++;
    this.filterPending = false;
    this.dispatch({ type: 'SET_PACKETS', packets: [] });
    this.send({ action: 'set_filter', expression });
  }

  getPackets(offset: number, limit: number): void {
    this.send({ action: 'get_packets', offset, limit });
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
