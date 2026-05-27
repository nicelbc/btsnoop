import { createContext, useContext } from 'react';
import { PacketSummary, PacketDetail } from '../types';

export interface PacketState {
  packets: PacketSummary[];
  selectedIndex: number | null;
  selectedDetail: PacketDetail | null;
  filter: string;
  wsConnected: boolean;
  sessionId: string | null;
  autoScroll: boolean;
  highlightRange: { offset: number; length: number } | null;
}

export type PacketAction =
  | { type: 'ADD_PACKETS'; packets: PacketSummary[] }
  | { type: 'SET_PACKETS'; packets: PacketSummary[] }
  | { type: 'SELECT_PACKET'; index: number | null }
  | { type: 'SET_DETAIL'; detail: PacketDetail | null }
  | { type: 'SET_FILTER'; filter: string }
  | { type: 'SET_WS_CONNECTED'; connected: boolean }
  | { type: 'SET_SESSION_ID'; sessionId: string | null }
  | { type: 'SET_AUTO_SCROLL'; enabled: boolean }
  | { type: 'SET_HIGHLIGHT_RANGE'; range: { offset: number; length: number } | null }
  | { type: 'RESET' };

export const initialState: PacketState = {
  packets: [],
  selectedIndex: null,
  selectedDetail: null,
  filter: '',
  wsConnected: false,
  sessionId: null,
  autoScroll: true,
  highlightRange: null,
};

export function packetReducer(state: PacketState, action: PacketAction): PacketState {
  switch (action.type) {
    case 'ADD_PACKETS':
      return { ...state, packets: [...state.packets, ...action.packets] };
    case 'SET_PACKETS':
      return { ...state, packets: action.packets };
    case 'SELECT_PACKET':
      return { ...state, selectedIndex: action.index, highlightRange: null };
    case 'SET_DETAIL':
      return { ...state, selectedDetail: action.detail };
    case 'SET_FILTER':
      return { ...state, filter: action.filter };
    case 'SET_WS_CONNECTED':
      return { ...state, wsConnected: action.connected };
    case 'SET_SESSION_ID':
      return { ...state, sessionId: action.sessionId };
    case 'SET_AUTO_SCROLL':
      return { ...state, autoScroll: action.enabled };
    case 'SET_HIGHLIGHT_RANGE':
      return { ...state, highlightRange: action.range };
    case 'RESET':
      return initialState;
    default:
      return state;
  }
}

export interface PacketContextType {
  state: PacketState;
  dispatch: React.Dispatch<PacketAction>;
}

export const PacketContext = createContext<PacketContextType | null>(null);

export function usePacketStore(): PacketContextType {
  const context = useContext(PacketContext);
  if (!context) {
    throw new Error('usePacketStore must be used within a PacketProvider');
  }
  return context;
}
