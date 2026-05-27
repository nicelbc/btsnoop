import React, { useRef, useEffect, useCallback } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { usePacketStore } from '../stores/packetStore';
import { PacketSummary } from '../types';

const PROTOCOL_COLORS: Record<string, string> = {
  HCI: 'border-l-proto-hci text-proto-hci',
  'HCI CMD': 'border-l-proto-hci text-proto-hci',
  'HCI EVT': 'border-l-proto-hci text-proto-hci',
  'HCI ACL': 'border-l-proto-hci text-proto-hci',
  'HCI SCO': 'border-l-proto-hci text-proto-hci',
  'HCI ISO': 'border-l-proto-hci text-proto-hci',
  L2CAP: 'border-l-proto-l2cap text-proto-l2cap',
  AVDTP: 'border-l-proto-avdtp text-proto-avdtp',
  A2DP: 'border-l-proto-avdtp text-proto-avdtp',
  ATT: 'border-l-proto-att text-proto-att',
  GATT: 'border-l-proto-att text-proto-att',
  SMP: 'border-l-proto-smp text-proto-smp',
  RFCOMM: 'border-l-proto-rfcomm text-proto-rfcomm',
  SDP: 'border-l-proto-sdp text-proto-sdp',
  AVCTP: 'border-l-proto-avctp text-proto-avctp',
  AVRCP: 'border-l-proto-avctp text-proto-avctp',
};

function getProtocolColor(protocol: string): string {
  return PROTOCOL_COLORS[protocol] || 'border-l-proto-default text-proto-default';
}

function formatTimestamp(ts: number): string {
  const seconds = ts.toFixed(6);
  return seconds;
}

interface PacketListProps {
  onSelectPacket: (index: number) => void;
}

export const PacketList: React.FC<PacketListProps> = ({ onSelectPacket }) => {
  const { state, dispatch } = usePacketStore();
  const { packets, selectedIndex, autoScroll, filter } = state;

  const parentRef = useRef<HTMLDivElement>(null);
  const lastCountRef = useRef(0);

  const filteredPackets = React.useMemo(() => {
    if (!filter) return packets;
    const lowerFilter = filter.toLowerCase();
    return packets.filter(
      (p) =>
        p.protocol.toLowerCase().includes(lowerFilter) ||
        p.summary.toLowerCase().includes(lowerFilter) ||
        p.type.toLowerCase().includes(lowerFilter)
    );
  }, [packets, filter]);

  const virtualizer = useVirtualizer({
    count: filteredPackets.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 24,
    overscan: 20,
  });

  // Auto-scroll to bottom when new packets arrive
  useEffect(() => {
    if (autoScroll && filteredPackets.length > lastCountRef.current) {
      virtualizer.scrollToIndex(filteredPackets.length - 1, { align: 'end' });
    }
    lastCountRef.current = filteredPackets.length;
  }, [filteredPackets.length, autoScroll, virtualizer]);

  const handleRowClick = useCallback(
    (packet: PacketSummary) => {
      dispatch({ type: 'SELECT_PACKET', index: packet.index });
      onSelectPacket(packet.index);
    },
    [dispatch, onSelectPacket]
  );

  const toggleAutoScroll = useCallback(() => {
    dispatch({ type: 'SET_AUTO_SCROLL', enabled: !autoScroll });
  }, [dispatch, autoScroll]);

  const handleFilterChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      dispatch({ type: 'SET_FILTER', filter: e.target.value });
    },
    [dispatch]
  );

  return (
    <div className="panel flex flex-col h-full">
      {/* Header */}
      <div className="panel-header">
        <span>Packet List ({filteredPackets.length} packets)</span>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Filter protocol..."
            value={filter}
            onChange={handleFilterChange}
            className="px-2 py-0.5 bg-ws-bg border border-ws-border rounded text-xs text-gray-200 w-48 focus:outline-none focus:border-ws-accent"
          />
          <button
            onClick={toggleAutoScroll}
            className={`px-2 py-0.5 rounded text-xs transition-colors ${
              autoScroll
                ? 'bg-ws-accent/20 text-ws-accent border border-ws-accent/50'
                : 'bg-ws-bg text-gray-500 border border-ws-border'
            }`}
            title="Auto-scroll to latest packets"
          >
            {autoScroll ? 'Auto' : 'Manual'}
          </button>
        </div>
      </div>

      {/* Column Headers */}
      <div className="flex items-center px-2 py-1 bg-ws-header text-xs text-gray-500 font-semibold border-b border-ws-border font-mono">
        <span className="w-14 shrink-0">No.</span>
        <span className="w-24 shrink-0">Time</span>
        <span className="w-8 shrink-0 text-center">Dir</span>
        <span className="w-20 shrink-0">Protocol</span>
        <span className="w-12 shrink-0 text-right">Len</span>
        <span className="flex-1 ml-3">Info / Summary</span>
      </div>

      {/* Virtual List */}
      <div ref={parentRef} className="flex-1 overflow-auto">
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const packet = filteredPackets[virtualRow.index];
            const isSelected = selectedIndex === packet.index;
            const protoColor = getProtocolColor(packet.protocol);

            return (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualRow.start}px)`,
                }}
                className={`packet-row flex items-center border-l-2 ${protoColor} ${
                  isSelected ? 'packet-row-selected' : ''
                }`}
                onClick={() => handleRowClick(packet)}
              >
                <span className="w-14 shrink-0 text-gray-500">{packet.index}</span>
                <span className="w-24 shrink-0 text-gray-400">
                  {formatTimestamp(packet.timestamp)}
                </span>
                <span className="w-8 shrink-0 text-center">
                  {packet.direction === 'sent' ? (
                    <span className="text-blue-400" title="Sent (Host to Controller)">
                      {'→'}
                    </span>
                  ) : (
                    <span className="text-green-400" title="Received (Controller to Host)">
                      {'←'}
                    </span>
                  )}
                </span>
                <span className="w-20 shrink-0 font-semibold">{packet.protocol}</span>
                <span className="w-12 shrink-0 text-right text-gray-500">{packet.length}</span>
                <span className="flex-1 ml-3 text-gray-300 truncate">{packet.summary}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
