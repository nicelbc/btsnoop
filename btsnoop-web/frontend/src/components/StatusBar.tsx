import React from 'react';
import { usePacketStore } from '../stores/packetStore';

export const StatusBar: React.FC = () => {
  const { state } = usePacketStore();
  const { packets, selectedIndex, selectedDetail, filter, wsConnected } = state;

  // Get file name from sessionStorage if available
  const fileName = typeof window !== 'undefined'
    ? sessionStorage.getItem('btsnoop_loaded_file') || ''
    : '';

  // Compute displayed count (all packets if no filter, otherwise packet list is already filtered)
  const totalCount = packets.length;
  const displayedCount = filter ? packets.length : totalCount;

  // Selected packet summary info
  const selectedPacket = selectedIndex !== null
    ? packets.find((p) => p.index === selectedIndex)
    : null;

  return (
    <div className="h-7 min-h-[28px] bg-ws-header border-t border-ws-border flex items-center px-3 gap-4 text-[11px] font-mono text-gray-400 select-none">
      {/* Connection status */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <span
          className={`status-dot ${
            wsConnected ? 'status-connected' : 'status-disconnected'
          }`}
        />
        <span className={wsConnected ? 'text-green-400' : 'text-red-400'}>
          {wsConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {/* Separator */}
      <div className="w-px h-3.5 bg-ws-border flex-shrink-0" />

      {/* Packet counts */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <span>
          Packets: <span className="text-gray-200">{totalCount}</span>
        </span>
        {filter && (
          <span>
            Displayed: <span className="text-gray-200">{displayedCount}</span>
          </span>
        )}
      </div>

      {/* Active filter indicator */}
      {filter && (
        <>
          <div className="w-px h-3.5 bg-ws-border flex-shrink-0" />
          <div className="flex items-center gap-1 text-blue-400 truncate max-w-[200px]">
            <svg className="w-3 h-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
              />
            </svg>
            <span className="truncate">{filter}</span>
          </div>
        </>
      )}

      {/* Separator */}
      <div className="w-px h-3.5 bg-ws-border flex-shrink-0" />

      {/* Selected packet info */}
      <div className="flex-1 truncate">
        {selectedPacket ? (
          <span>
            Selected: <span className="text-gray-200">#{selectedPacket.index}</span>
            {' | '}
            <span className="text-gray-300">{selectedPacket.protocol}</span>
            {' | '}
            <span className="text-gray-300">{selectedPacket.length} bytes</span>
            {' | '}
            <span className="text-gray-400 truncate">{selectedPacket.summary}</span>
          </span>
        ) : (
          <span className="text-gray-500">No packet selected</span>
        )}
      </div>

      {/* File name */}
      {fileName && (
        <>
          <div className="w-px h-3.5 bg-ws-border flex-shrink-0" />
          <div className="flex items-center gap-1 text-gray-500 flex-shrink-0 max-w-[180px]">
            <svg className="w-3 h-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <span className="truncate">{fileName}</span>
          </div>
        </>
      )}
    </div>
  );
};

export default StatusBar;
