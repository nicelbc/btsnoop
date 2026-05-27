import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import React, { useReducer } from 'react';
import { FilterBar } from '../FilterBar';
import {
  PacketContext,
  PacketState,
  PacketAction,
  packetReducer,
  initialState,
} from '../../stores/packetStore';

function renderWithStore(ui: React.ReactElement, stateOverrides: Partial<PacketState> = {}) {
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

describe('FilterBar', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders input field with placeholder', () => {
    renderWithStore(<FilterBar />);
    const input = screen.getByPlaceholderText(/Filter: e.g./);
    expect(input).toBeInTheDocument();
    expect(input.tagName).toBe('INPUT');
  });

  it('shows green background for valid filter syntax', async () => {
    renderWithStore(<FilterBar />);
    const input = screen.getByPlaceholderText(/Filter: e.g./);

    // Type a valid filter expression
    await userEvent.type(input, 'hci.type == command');

    // The input should have green border/bg classes
    expect(input.className).toContain('border-green-600');
    expect(input.className).toContain('bg-green-950');
  });

  it('shows red background for invalid filter', async () => {
    renderWithStore(<FilterBar />);
    const input = screen.getByPlaceholderText(/Filter: e.g./);

    // Type an invalid filter (trailing logical operator)
    await userEvent.type(input, 'hci.type == command &&');

    // The input should have red border/bg classes
    expect(input.className).toContain('border-red-600');
    expect(input.className).toContain('bg-red-950');
  });

  it('stores filter history in localStorage', async () => {
    renderWithStore(<FilterBar />, { wsConnected: false });
    const input = screen.getByPlaceholderText(/Filter: e.g./);

    // Type a valid filter and apply
    await userEvent.type(input, 'hci.type == command');
    const applyButton = screen.getByText('Apply');
    await userEvent.click(applyButton);

    // Check localStorage
    const history = JSON.parse(localStorage.getItem('btsnoop_filter_history') || '[]');
    expect(history).toContain('hci.type == command');
  });

  it('shows autocomplete suggestions', async () => {
    renderWithStore(<FilterBar />);
    const input = screen.getByPlaceholderText(/Filter: e.g./);

    // Type partial field name
    await userEvent.type(input, 'hci');

    // Should show suggestions dropdown containing hci fields
    expect(screen.getByText('hci.type')).toBeInTheDocument();
    expect(screen.getByText('hci.opcode')).toBeInTheDocument();
  });
});
