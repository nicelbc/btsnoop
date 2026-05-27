export interface PacketSummary {
  index: number;
  timestamp: number;
  direction: 'sent' | 'received';
  type: string;
  protocol: string;
  summary: string;
  length: number;
}

export interface DecodedField {
  name: string;
  value: string;
  offset: number;
  length: number;
  children?: DecodedField[];
}

export interface DecodedLayer {
  protocol: string;
  summary: string;
  fields: DecodedField[];
  payload_offset: number;
  payload_length: number;
}

export interface PacketDetail {
  index: number;
  layers: DecodedLayer[];
  raw_hex: string;
}

// WebSocket message types
export interface WsPacketBatch {
  type: 'packet_batch';
  packets: PacketSummary[];
}

export interface WsPacketDetail {
  type: 'packet_detail';
  detail: PacketDetail;
}

export interface WsError {
  type: 'error';
  message: string;
}

export interface WsConnected {
  type: 'connected';
  session_id: string;
  total_packets: number;
}

export type WsMessage = WsPacketBatch | WsPacketDetail | WsError | WsConnected;

// Commands sent to server
export interface CmdGetDetail {
  cmd: 'get_detail';
  index: number;
}

export interface CmdSetFilter {
  cmd: 'set_filter';
  filter: string;
}

export type WsCommand = CmdGetDetail | CmdSetFilter;
