import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React, { useReducer } from 'react';
import { PacketList } from '../PacketList';
import {
  PacketContext,
  PacketState,
  PacketAction,
  packetReducer,
  initialState,
} from '../../stores/packetStore';
import { PacketSummary } from '../../types';

// Mock @tanstack/react-virtual because it needs a real scrollable container
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: ({ count }: any) => ({
    getVirtualItems: () =>
      Array.from({ length: count }, (_, i) => ({
        index: i,
        key: `item-${i}`,
        start: i * 24,
        size: 24,
      })),
    getTotalSize: () => count * 24,
    scrollToIndex: vi.fn(),
    measureElement: vi.fn(),
  }),
}));

const samplePackets: PacketSummary[] = [
  {
    index: 0,
    timestamp_us: 123,
    timestamp: '0.000123',
    direction: 'sent',
    protocol: 'HCI CMD',
    summary: 'Reset',
    raw_length: 3,
    included_length: 3,
    layers: [],
  },
  {
    index: 1,
    timestamp_us: 1456,
    timestamp: '0.001456',
    direction: 'received',
    protocol: 'L2CAP',
    summary: 'Connection Request',
    raw_length: 12,
    included_length: 12,
    layers: [],
  },
  {
    index: 2,
    timestamp_us: 2789,
    timestamp: '0.002789',
    direction: 'sent',
    protocol: 'ATT',
    summary: 'Read Request',
    raw_length: 7,
    included_length: 7,
    layers: [],
  },
];

function renderWithStore(
  ui: React.ReactElement,
  stateOverrides: Partial<PacketState> = {}
) {
  const state: PacketState = { ...initialState, ...stateOverrides };

  function Wrapper({ children }: { children: React.ReactNode }) {
    const [currentState, dispatch] = useReducer(packetReducer, state);
    return (
      <PacketContext.Provider value={{ state: currentState, dispatch }}>
        {children}
      </PacketContext.Provider>
    );
  }

  return render(ui, { wrapper: Wrapper });
}

describe('PacketList', () => {
  it('renders packet rows with correct columns', () => {
    const onSelectPacket = vi.fn();
    renderWithStore(<PacketList onSelectPacket={onSelectPacket} />, {
      packets: samplePackets,
    });

    // Column headers
    expect(screen.getByText('No.')).toBeInTheDocument();
    expect(screen.getByText('Time')).toBeInTheDocument();
    expect(screen.getByText('Dir')).toBeInTheDocument();
    expect(screen.getByText('Protocol')).toBeInTheDocument();
    expect(screen.getByText('Len')).toBeInTheDocument();
    expect(screen.getByText('Info / Summary')).toBeInTheDocument();

    // Packet data
    expect(screen.getByText('HCI CMD')).toBeInTheDocument();
    expect(screen.getByText('L2CAP')).toBeInTheDocument();
    expect(screen.getByText('ATT')).toBeInTheDocument();
    expect(screen.getByText('Reset')).toBeInTheDocument();
    expect(screen.getByText('Connection Request')).toBeInTheDocument();
    expect(screen.getByText('Read Request')).toBeInTheDocument();
  });

  it('color codes by protocol', () => {
    const onSelectPacket = vi.fn();
    const { container } = renderWithStore(
      <PacketList onSelectPacket={onSelectPacket} />,
      { packets: samplePackets }
    );

    // Find rows with protocol-specific border color classes
    const rows = container.querySelectorAll('.packet-row');
    expect(rows.length).toBe(3);

    // HCI CMD row should have hci color class
    expect(rows[0].className).toContain('border-l-proto-hci');
    // L2CAP row should have l2cap color class
    expect(rows[1].className).toContain('border-l-proto-l2cap');
    // ATT row should have att color class
    expect(rows[2].className).toContain('border-l-proto-att');
  });

  it('handles empty packet list', () => {
    const onSelectPacket = vi.fn();
    renderWithStore(<PacketList onSelectPacket={onSelectPacket} />, {
      packets: [],
    });

    // Should show 0 packets in header
    expect(screen.getByText('Packet List (0 packets)')).toBeInTheDocument();
  });

  it('calls selection handler on row click', () => {
    const onSelectPacket = vi.fn();
    const { container } = renderWithStore(
      <PacketList onSelectPacket={onSelectPacket} />,
      { packets: samplePackets }
    );

    // Click on the first packet row
    const rows = container.querySelectorAll('.packet-row');
    fireEvent.click(rows[0]);

    expect(onSelectPacket).toHaveBeenCalledWith(0);
  });
});
