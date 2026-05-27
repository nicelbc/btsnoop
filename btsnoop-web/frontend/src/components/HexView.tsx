import React, { useMemo } from 'react';
import { usePacketStore } from '../stores/packetStore';

const BYTES_PER_ROW = 16;

function hexToBytes(hex: string): number[] {
  const bytes: number[] = [];
  const clean = hex.replace(/\s/g, '');
  for (let i = 0; i < clean.length; i += 2) {
    bytes.push(parseInt(clean.substring(i, i + 2), 16));
  }
  return bytes;
}

function byteToHex(b: number): string {
  return b.toString(16).padStart(2, '0');
}

function byteToAscii(b: number): string {
  return b >= 32 && b <= 126 ? String.fromCharCode(b) : '.';
}

function formatOffset(offset: number): string {
  return offset.toString(16).padStart(8, '0');
}

export const HexView: React.FC = () => {
  const { state } = usePacketStore();
  const { selectedDetail, highlightRange } = state;

  const bytes = useMemo(() => {
    if (!selectedDetail?.raw_hex) return [];
    return hexToBytes(selectedDetail.raw_hex);
  }, [selectedDetail?.raw_hex]);

  const rows = useMemo(() => {
    const result: { offset: number; bytes: number[] }[] = [];
    for (let i = 0; i < bytes.length; i += BYTES_PER_ROW) {
      result.push({
        offset: i,
        bytes: bytes.slice(i, i + BYTES_PER_ROW),
      });
    }
    return result;
  }, [bytes]);

  const isHighlighted = (byteIndex: number): boolean => {
    if (!highlightRange) return false;
    return (
      byteIndex >= highlightRange.offset &&
      byteIndex < highlightRange.offset + highlightRange.length
    );
  };

  if (!selectedDetail) {
    return (
      <div className="panel flex flex-col h-full">
        <div className="panel-header">
          <span>Hex Dump</span>
        </div>
        <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
          Select a packet to view hex data
        </div>
      </div>
    );
  }

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header">
        <span>Hex Dump</span>
        <span className="text-gray-600">{bytes.length} bytes</span>
      </div>
      <div className="flex-1 overflow-auto p-2">
        <div className="font-mono text-xs leading-5">
          {rows.map((row) => (
            <div key={row.offset} className="flex whitespace-nowrap">
              {/* Offset */}
              <span className="text-gray-600 w-20 shrink-0 select-none">
                {formatOffset(row.offset)}
              </span>

              {/* Hex bytes */}
              <span className="shrink-0" style={{ width: '400px' }}>
                {row.bytes.map((b, i) => {
                  const globalIdx = row.offset + i;
                  const highlighted = isHighlighted(globalIdx);
                  return (
                    <span key={i}>
                      <span
                        className={`hex-byte ${highlighted ? 'hex-byte-highlighted' : 'text-gray-300'}`}
                      >
                        {byteToHex(b)}
                      </span>
                      {i === 7 && <span className="text-gray-700"> </span>}
                    </span>
                  );
                })}
                {/* Pad remaining space if row is not full */}
                {row.bytes.length < BYTES_PER_ROW &&
                  Array.from({ length: BYTES_PER_ROW - row.bytes.length }).map((_, i) => (
                    <span key={`pad-${i}`} className="hex-byte">
                      {'  '}
                    </span>
                  ))}
              </span>

              {/* ASCII */}
              <span className="ml-4 text-gray-500 select-none">
                {row.bytes.map((b, i) => {
                  const globalIdx = row.offset + i;
                  const highlighted = isHighlighted(globalIdx);
                  return (
                    <span
                      key={i}
                      className={highlighted ? 'text-blue-300 bg-blue-900/40' : ''}
                    >
                      {byteToAscii(b)}
                    </span>
                  );
                })}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
