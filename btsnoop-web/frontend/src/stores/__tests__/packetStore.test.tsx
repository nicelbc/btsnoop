import { describe, it, expect } from 'vitest';
import { packetReducer, initialState, PacketState } from '../packetStore';
import { PacketSummary, PacketDetail } from '../../types';

const samplePackets: PacketSummary[] = [
  {
    index: 0,
    timestamp_us: 100,
    timestamp: '0.000100',
    direction: 'sent',
    protocol: 'HCI CMD',
    summary: 'Reset',
    raw_length: 3,
    included_length: 3,
    layers: [],
  },
  {
    index: 1,
    timestamp_us: 1200,
    timestamp: '0.001200',
    direction: 'received',
    protocol: 'HCI EVT',
    summary: 'Command Complete',
    raw_length: 7,
    included_length: 7,
    layers: [],
  },
];

const morePackets: PacketSummary[] = [
  {
    index: 2,
    timestamp_us: 2300,
    timestamp: '0.002300',
    direction: 'sent',
    protocol: 'L2CAP',
    summary: 'Data',
    raw_length: 20,
    included_length: 20,
    layers: [],
  },
];

describe('packetStore reducer', () => {
  it('ADD_PACKETS action appends packets', () => {
    const stateWithPackets: PacketState = {
      ...initialState,
      packets: samplePackets,
    };

    const newState = packetReducer(stateWithPackets, {
      type: 'ADD_PACKETS',
      packets: morePackets,
    });

    expect(newState.packets).toHaveLength(3);
    expect(newState.packets[0]).toEqual(samplePackets[0]);
    expect(newState.packets[1]).toEqual(samplePackets[1]);
    expect(newState.packets[2]).toEqual(morePackets[0]);
  });

  it('ADD_PACKETS to empty state adds packets', () => {
    const newState = packetReducer(initialState, {
      type: 'ADD_PACKETS',
      packets: samplePackets,
    });

    expect(newState.packets).toHaveLength(2);
    expect(newState.packets).toEqual(samplePackets);
  });

  it('SELECT_PACKET updates selection and clears highlight', () => {
    const stateWithHighlight: PacketState = {
      ...initialState,
      packets: samplePackets,
      highlightRange: { offset: 0, length: 4 },
    };

    const newState = packetReducer(stateWithHighlight, {
      type: 'SELECT_PACKET',
      index: 1,
    });

    expect(newState.selectedIndex).toBe(1);
    expect(newState.highlightRange).toBeNull();
  });

  it('SET_FILTER updates filter state', () => {
    const newState = packetReducer(initialState, {
      type: 'SET_FILTER',
      filter: 'hci.type == command',
    });

    expect(newState.filter).toBe('hci.type == command');
  });

  it('SET_FILTER with empty string clears filter', () => {
    const stateWithFilter: PacketState = {
      ...initialState,
      filter: 'hci.type == event',
    };

    const newState = packetReducer(stateWithFilter, {
      type: 'SET_FILTER',
      filter: '',
    });

    expect(newState.filter).toBe('');
  });

  it('RESET resets all state to initial', () => {
    const modifiedState: PacketState = {
      packets: samplePackets,
      selectedIndex: 1,
      selectedDetail: {
        packet: samplePackets[1],
        raw_hex: 'aabb',
        flags: 0,
      },
      filter: 'hci.type',
      wsConnected: true,
      sessionId: 'sess-123',
      autoScroll: false,
      highlightRange: { offset: 2, length: 3 },
    };

    const newState = packetReducer(modifiedState, { type: 'RESET' });

    expect(newState).toEqual(initialState);
    expect(newState.packets).toHaveLength(0);
    expect(newState.selectedIndex).toBeNull();
    expect(newState.selectedDetail).toBeNull();
    expect(newState.filter).toBe('');
    expect(newState.wsConnected).toBe(false);
    expect(newState.sessionId).toBeNull();
    expect(newState.autoScroll).toBe(true);
    expect(newState.highlightRange).toBeNull();
  });

  it('SET_DETAIL sets the packet detail', () => {
    const detail: PacketDetail = {
      packet: samplePackets[0],
      raw_hex: '030c00',
      flags: 0,
    };

    const newState = packetReducer(initialState, {
      type: 'SET_DETAIL',
      detail,
    });

    expect(newState.selectedDetail).toEqual(detail);
  });

  it('SET_WS_CONNECTED updates connection status', () => {
    const newState = packetReducer(initialState, {
      type: 'SET_WS_CONNECTED',
      connected: true,
    });

    expect(newState.wsConnected).toBe(true);
  });

  it('SET_HIGHLIGHT_RANGE updates the highlight', () => {
    const newState = packetReducer(initialState, {
      type: 'SET_HIGHLIGHT_RANGE',
      range: { offset: 5, length: 10 },
    });

    expect(newState.highlightRange).toEqual({ offset: 5, length: 10 });
  });
});
