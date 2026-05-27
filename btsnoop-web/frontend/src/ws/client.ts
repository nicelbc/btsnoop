import { WsMessage, WsCommand } from '../types';
import { PacketAction } from '../stores/packetStore';

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private dispatch: React.Dispatch<PacketAction>;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private sessionId: string;

  constructor(sessionId: string, dispatch: React.Dispatch<PacketAction>) {
    this.sessionId = sessionId;
    this.dispatch = dispatch;
  }

  connect(): void {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/${this.sessionId}`;

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
        this.dispatch({ type: 'ADD_PACKETS', packets: msg.packets });
        break;
      case 'packet_detail':
        this.dispatch({ type: 'SET_DETAIL', detail: msg.detail });
        break;
      case 'connected':
        this.dispatch({ type: 'SET_SESSION_ID', sessionId: msg.session_id });
        break;
      case 'error':
        console.error('[WS] Server error:', msg.message);
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
    this.send({ cmd: 'get_detail', index });
  }

  setFilter(filter: string): void {
    this.send({ cmd: 'set_filter', filter });
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
