import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import React from 'react';
import { HexView } from '../HexView';
import {
  PacketContext,
  PacketState,
  PacketAction,
  initialState,
} from '../../stores/packetStore';
import { PacketDetail, PacketSummary } from '../../types';

const samplePacket: PacketSummary = {
  index: 0,
  timestamp_us: 0,
  timestamp: '0.000000',
  direction: 'sent',
  protocol: 'HCI CMD',
  summary: 'Reset',
  raw_length: 3,
  included_length: 3,
  layers: [],
};

function makeDetail(rawHex: string): PacketDetail {
  return {
    packet: samplePacket,
    raw_hex: rawHex,
    flags: 0,
  };
}

function renderWithStore(ui: React.ReactElement, stateOverrides: Partial<PacketState> = {}) {
  const state: PacketState = { ...initialState, ...stateOverrides };
  const dispatch: React.Dispatch<PacketAction> = () => {};

  return render(
    <PacketContext.Provider value={{ state, dispatch }}>
      {ui}
    </PacketContext.Provider>
  );
}

describe('HexView', () => {
  it('renders placeholder when no detail is selected', () => {
    renderWithStore(<HexView />);
    expect(screen.getByText('Select a packet to view hex data')).toBeInTheDocument();
  });

  it('renders hex dump with correct format (offset | hex | ascii)', () => {
    // 4 bytes: 0x48 0x65 0x6c 0x6c = "Hell"
    renderWithStore(<HexView />, {
      selectedDetail: makeDetail('48656c6c'),
    });

    // Should show offset "00000000"
    expect(screen.getByText('00000000')).toBeInTheDocument();

    // Should show byte count
    expect(screen.getByText('4 bytes')).toBeInTheDocument();

    // Should show hex and ASCII
    const row = screen.getByText('00000000').closest('.flex.whitespace-nowrap');
    expect(row).toBeInTheDocument();
    expect(row?.textContent).toContain('48');
    expect(row?.textContent).toContain('65');
    expect(row?.textContent).toContain('6c');
    expect(row?.textContent).toContain('Hell');
  });

  it('highlights bytes in specified range', () => {
    // 8 bytes
    const { container } = renderWithStore(<HexView />, {
      selectedDetail: makeDetail('0102030405060708'),
      highlightRange: { offset: 2, length: 3 }, // bytes at index 2, 3, 4
    });

    // Find highlighted hex bytes
    const highlightedHexBytes = container.querySelectorAll('.hex-byte-highlighted');
    expect(highlightedHexBytes.length).toBe(3);

    // Check the highlighted values are bytes at offset 2,3,4 = 03, 04, 05
    const highlightedTexts = Array.from(highlightedHexBytes).map((el) => el.textContent);
    expect(highlightedTexts).toContain('03');
    expect(highlightedTexts).toContain('04');
    expect(highlightedTexts).toContain('05');
  });

  it('handles empty data', () => {
    renderWithStore(<HexView />, {
      selectedDetail: makeDetail(''),
    });

    // Should show "0 bytes" and no rows
    expect(screen.getByText('0 bytes')).toBeInTheDocument();
    expect(screen.queryByText('00000000')).not.toBeInTheDocument();
  });

  it('shows 16 bytes per row', () => {
    // Create 32 bytes (2 full rows)
    const { container } = renderWithStore(<HexView />, {
      selectedDetail: makeDetail('00'.repeat(32)),
    });

    // Should have exactly 2 offset labels
    expect(screen.getByText('00000000')).toBeInTheDocument();
    expect(screen.getByText('00000010')).toBeInTheDocument();

    // Each row should be present
    const rows = container.querySelectorAll('.flex.whitespace-nowrap');
    expect(rows.length).toBe(2);
  });
});
