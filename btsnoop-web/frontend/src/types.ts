export interface PacketSummary {
  index: number;
  timestamp_us: number;
  timestamp: string;
  direction: 'sent' | 'received';
  protocol: string;
  summary: string;
  raw_length: number;
  included_length: number;
  layers: DecodedLayer[];
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
  sublayers?: DecodedLayer[];
  payload_offset: number;
  payload_length: number;
}

export interface PacketDetail {
  packet: PacketSummary;
  raw_hex: string;
  flags: number;
}

// WebSocket message types
export interface WsPacketBatch {
  type: 'packet_batch';
  packets: PacketSummary[];
}

export interface WsPacketDetail {
  type: 'packet_detail';
  packet: PacketSummary;
  raw_hex: string;
  flags: number;
}

export interface WsFilterApplied {
  type: 'filter_applied';
  expression: string;
  matched: number;
  total: number;
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

export type WsMessage = WsPacketBatch | WsPacketDetail | WsFilterApplied | WsError | WsConnected;

// Commands sent to server
export interface CmdGetDetail {
  action: 'get_detail';
  index: number;
}

export interface CmdSetFilter {
  action: 'set_filter';
  expression: string;
}

export interface CmdGetPackets {
  action: 'get_packets';
  offset: number;
  limit: number;
}

export type WsCommand = CmdGetDetail | CmdSetFilter | CmdGetPackets;
