import React, { useState, useEffect, useCallback } from 'react';
import { PacketSummary } from '../types';
import { usePacketStore } from '../stores/packetStore';

interface ContextMenuProps {
  x: number;
  y: number;
  packet: PacketSummary;
  onClose: () => void;
}

export const ContextMenu: React.FC<ContextMenuProps> = ({ x, y, packet, onClose }) => {
  const { dispatch } = usePacketStore();

  useEffect(() => {
    const handleClick = () => onClose();
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('click', handleClick);
    document.addEventListener('keydown', handleEsc);
    return () => {
      document.removeEventListener('click', handleClick);
      document.removeEventListener('keydown', handleEsc);
    };
  }, [onClose]);

  const applyFilter = useCallback((filter: string) => {
    dispatch({ type: 'SET_FILTER', filter });
    window.dispatchEvent(new CustomEvent('btsnoop:apply_filter', { detail: { filter } }));
    onClose();
  }, [dispatch, onClose]);

  const items = [
    { label: `仅显示协议: ${packet.protocol}`, action: () => applyFilter(`protocol == ${packet.protocol.toLowerCase()}`) },
    { label: `仅显示方向: ${packet.direction === 'sent' ? '发送' : '接收'}`, action: () => applyFilter(`direction == ${packet.direction}`) },
    { label: `排除协议: ${packet.protocol}`, action: () => applyFilter(`protocol != ${packet.protocol.toLowerCase()}`) },
    { label: '清除过滤', action: () => applyFilter('') },
  ];

  return (
    <div
      className="fixed z-50 bg-ws-panel border border-ws-border rounded shadow-xl py-1 min-w-[200px]"
      style={{ left: x, top: y }}
    >
      {items.map((item, i) => (
        <button
          key={i}
          className="w-full text-left px-4 py-1.5 text-xs text-gray-200 hover:bg-ws-hover hover:text-white transition-colors"
          onClick={(e) => { e.stopPropagation(); item.action(); }}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
};

export interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  packet: PacketSummary | null;
}

export const initialContextMenu: ContextMenuState = { visible: false, x: 0, y: 0, packet: null };
