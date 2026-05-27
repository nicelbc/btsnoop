import React, { useCallback } from 'react';
import { usePacketStore } from '../stores/packetStore';

const PROTO_FILTERS = [
  { label: '全部', filter: '', color: 'bg-gray-600' },
  { label: 'HCI', filter: 'protocol == hci_cmd || protocol == hci_evt', color: 'bg-blue-600' },
  { label: 'L2CAP', filter: 'protocol == l2cap || protocol == l2cap_sig', color: 'bg-green-600' },
  { label: 'A2DP', filter: 'protocol == avdtp', color: 'bg-purple-600' },
  { label: 'AVRCP', filter: 'protocol == avrcp', color: 'bg-pink-600' },
  { label: 'ATT/BLE', filter: 'protocol == att', color: 'bg-orange-600' },
  { label: 'SMP', filter: 'protocol == smp', color: 'bg-teal-600' },
  { label: 'HFP', filter: 'protocol == hfp', color: 'bg-red-600' },
  { label: 'RFCOMM', filter: 'protocol == rfcomm', color: 'bg-yellow-700' },
  { label: 'SDP', filter: 'protocol == sdp', color: 'bg-indigo-600' },
];

export const ProtoFilterBar: React.FC = () => {
  const { state, dispatch } = usePacketStore();
  const active = state.filter;

  const handleClick = useCallback((filter: string) => {
    dispatch({ type: 'SET_FILTER', filter });
    window.dispatchEvent(new CustomEvent('btsnoop:apply_filter', { detail: { filter } }));
  }, [dispatch]);

  return (
    <div className="flex items-center gap-1 px-2 py-1 bg-ws-header border-b border-ws-border overflow-x-auto">
      <span className="text-[10px] text-gray-500 mr-1 shrink-0">协议:</span>
      {PROTO_FILTERS.map(({ label, filter, color }) => {
        const isActive = active === filter;
        return (
          <button
            key={label}
            onClick={() => handleClick(filter)}
            className={`px-2 py-0.5 rounded text-[11px] font-medium transition-all shrink-0 ${
              isActive
                ? `${color} text-white shadow-sm ring-1 ring-white/20`
                : 'bg-ws-bg text-gray-400 hover:text-gray-200 hover:bg-ws-hover border border-ws-border'
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
};
