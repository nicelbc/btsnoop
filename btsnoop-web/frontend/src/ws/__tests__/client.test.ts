import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { WebSocketClient } from '../client';

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSING = 2;
  readonly CLOSED = 3;

  url: string;
  readyState: number = 0; // CONNECTING
  onopen: ((ev: any) => void) | null = null;
  onmessage: ((ev: any) => void) | null = null;
  onclose: ((ev: any) => void) | null = null;
  onerror: ((ev: any) => void) | null = null;
  sentMessages: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = 3; // CLOSED
    if (this.onclose) {
      this.onclose({});
    }
  }

  // Test helpers
  simulateOpen() {
    this.readyState = 1; // OPEN
    if (this.onopen) this.onopen({});
  }

  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) });
    }
  }

  simulateClose() {
    this.readyState = 3;
    if (this.onclose) this.onclose({});
  }

  simulateError(error: any) {
    if (this.onerror) this.onerror(error);
  }
}

describe('WebSocketClient', () => {
  let originalWebSocket: typeof WebSocket;

  beforeEach(() => {
    MockWebSocket.instances = [];
    originalWebSocket = globalThis.WebSocket;
    (globalThis as any).WebSocket = MockWebSocket;
    vi.useFakeTimers();
  });

  afterEach(() => {
    (globalThis as any).WebSocket = originalWebSocket;
    vi.useRealTimers();
  });

  it('creates WebSocket connection with correct URL', () => {
    Object.defineProperty(window, 'location', {
      value: { protocol: 'http:', host: 'localhost:3000' },
      writable: true,
    });

    const dispatch = vi.fn();
    const client = new WebSocketClient('session-abc', dispatch);
    client.connect();

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe('ws://localhost:3000/ws/session-abc');

    client.disconnect();
  });

  it('handles packet_batch messages', () => {
    Object.defineProperty(window, 'location', {
      value: { protocol: 'http:', host: 'localhost:3000' },
      writable: true,
    });

    const dispatch = vi.fn();
    const client = new WebSocketClient('session-1', dispatch);
    client.connect();

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    // Clear the SET_WS_CONNECTED dispatch
    dispatch.mockClear();

    const batchMessage = {
      type: 'packet_batch',
      packets: [
        {
          index: 0,
          timestamp_us: 1000,
          timestamp: '0.001000',
          direction: 'sent',
          protocol: 'HCI CMD',
          summary: 'Reset',
          raw_length: 3,
          included_length: 3,
          layers: [],
        },
      ],
    };

    ws.simulateMessage(batchMessage);

    expect(dispatch).toHaveBeenCalledWith({
      type: 'ADD_PACKETS',
      packets: batchMessage.packets,
    });

    client.disconnect();
  });

  it('handles packet_detail messages', () => {
    Object.defineProperty(window, 'location', {
      value: { protocol: 'http:', host: 'localhost:3000' },
      writable: true,
    });

    const dispatch = vi.fn();
    const client = new WebSocketClient('session-2', dispatch);
    client.connect();

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();
    dispatch.mockClear();

    const detailMessage = {
      type: 'packet_detail',
      packet: {
        index: 0,
        timestamp_us: 1000,
        timestamp: '0.001000',
        direction: 'sent',
        protocol: 'HCI CMD',
        summary: 'Reset',
        raw_length: 3,
        included_length: 3,
        layers: [],
      },
      raw_hex: '030c00',
      flags: 0,
    };

    ws.simulateMessage(detailMessage);

    expect(dispatch).toHaveBeenCalledWith({
      type: 'SET_DETAIL',
      detail: {
        packet: detailMessage.packet,
        raw_hex: detailMessage.raw_hex,
        flags: detailMessage.flags,
      },
    });

    client.disconnect();
  });

  it('reconnects on disconnect', () => {
    Object.defineProperty(window, 'location', {
      value: { protocol: 'http:', host: 'localhost:3000' },
      writable: true,
    });

    const dispatch = vi.fn();
    const client = new WebSocketClient('session-3', dispatch);
    client.connect();

    expect(MockWebSocket.instances).toHaveLength(1);

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();
    dispatch.mockClear();

    // Simulate connection close
    ws.simulateClose();

    expect(dispatch).toHaveBeenCalledWith({
      type: 'SET_WS_CONNECTED',
      connected: false,
    });

    // Should reconnect after 3 seconds
    expect(MockWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(3000);
    expect(MockWebSocket.instances).toHaveLength(2);

    // New connection should use the same URL
    expect(MockWebSocket.instances[1].url).toBe('ws://localhost:3000/ws/session-3');

    client.disconnect();
  });

  it('dispatches SET_WS_CONNECTED on open', () => {
    Object.defineProperty(window, 'location', {
      value: { protocol: 'https:', host: 'example.com' },
      writable: true,
    });

    const dispatch = vi.fn();
    const client = new WebSocketClient('session-4', dispatch);
    client.connect();

    // Should use wss: for https:
    expect(MockWebSocket.instances[0].url).toBe('wss://example.com/ws/session-4');

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    expect(dispatch).toHaveBeenCalledWith({
      type: 'SET_WS_CONNECTED',
      connected: true,
    });

    client.disconnect();
  });

  it('sends commands when connected', () => {
    Object.defineProperty(window, 'location', {
      value: { protocol: 'http:', host: 'localhost:3000' },
      writable: true,
    });

    const dispatch = vi.fn();
    const client = new WebSocketClient('session-5', dispatch);
    client.connect();

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    client.requestDetail(5);
    expect(ws.sentMessages).toHaveLength(1);
    expect(JSON.parse(ws.sentMessages[0])).toEqual({ action: 'get_detail', index: 5 });

    client.setFilter('hci.type == command');
    expect(ws.sentMessages).toHaveLength(2);
    expect(JSON.parse(ws.sentMessages[1])).toEqual({
      action: 'set_filter',
      expression: 'hci.type == command',
    });

    client.disconnect();
  });
});
