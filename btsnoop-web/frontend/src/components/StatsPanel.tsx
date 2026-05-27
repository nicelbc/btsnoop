import React, { useEffect, useState } from 'react';

interface StatsPanelProps {
  sessionId: string | null;
  visible: boolean;
  onClose: () => void;
}

interface ProtocolStat {
  protocol: string;
  count: number;
  percentage: number;
}

interface ConnectionStat {
  handle: string;
  packets: number;
}

interface SessionStats {
  total_packets: number;
  duration_seconds: number;
  packets_per_second: number;
  sent_count: number;
  received_count: number;
  protocols: ProtocolStat[];
  top_connections: ConnectionStat[];
}

const PROTOCOL_COLORS: Record<string, string> = {
  HCI: '#5c9eff',
  'HCI CMD': '#5c9eff',
  'HCI EVT': '#5c9eff',
  'HCI ACL': '#5c9eff',
  'HCI SCO': '#5c9eff',
  'HCI ISO': '#5c9eff',
  L2CAP: '#4caf50',
  AVDTP: '#ab47bc',
  A2DP: '#ab47bc',
  ATT: '#ff9800',
  GATT: '#ff9800',
  SMP: '#f44336',
  RFCOMM: '#00bcd4',
  SDP: '#8bc34a',
  AVCTP: '#e91e63',
  AVRCP: '#e91e63',
};

function getProtocolBarColor(protocol: string): string {
  return PROTOCOL_COLORS[protocol] || '#78909c';
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins < 60) return `${mins}m ${secs.toFixed(0)}s`;
  const hours = Math.floor(mins / 60);
  const remainMins = mins % 60;
  return `${hours}h ${remainMins}m`;
}

export const StatsPanel: React.FC<StatsPanelProps> = ({ sessionId, visible, onClose }) => {
  const [stats, setStats] = useState<SessionStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId || !visible) {
      setStats(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(`/api/sessions/${sessionId}/stats`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: SessionStats) => {
        if (!cancelled) {
          setStats(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message || 'Failed to fetch stats');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId, visible]);

  if (!visible) return null;

  const totalDirection = stats ? stats.sent_count + stats.received_count : 0;
  const sentPercent = totalDirection > 0 ? (stats!.sent_count / totalDirection) * 100 : 50;

  return (
    <div className="fixed top-9 right-0 bottom-6 w-72 bg-ws-panel border-l border-ws-border z-50 flex flex-col shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-ws-header border-b border-ws-border">
        <h2 className="text-xs font-semibold text-gray-200 uppercase tracking-wide">
          Statistics
        </h2>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-100 transition-colors p-0.5 rounded hover:bg-ws-hover"
          title="Close stats panel"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="text-xs text-gray-400 animate-pulse">Loading stats...</div>
          </div>
        )}

        {error && (
          <div className="text-xs text-red-400 bg-red-900/20 border border-red-800/30 rounded px-2 py-1.5">
            {error}
          </div>
        )}

        {!loading && !error && !stats && !sessionId && (
          <div className="text-xs text-gray-500 text-center py-8">
            No active session
          </div>
        )}

        {stats && (
          <>
            {/* Overview Section */}
            <Section title="Overview">
              <StatRow label="Total Packets" value={stats.total_packets.toLocaleString()} />
              <StatRow label="Duration" value={formatDuration(stats.duration_seconds)} />
              <StatRow label="Rate" value={`${stats.packets_per_second.toFixed(1)} pkt/s`} />
            </Section>

            {/* Direction Split */}
            <Section title="Direction">
              <div className="space-y-1.5">
                <div className="flex justify-between text-[10px] text-gray-400">
                  <span>Sent: {stats.sent_count}</span>
                  <span>Received: {stats.received_count}</span>
                </div>
                <div className="h-3 rounded-sm overflow-hidden flex bg-ws-bg border border-ws-border">
                  <div
                    className="h-full transition-all"
                    style={{
                      width: `${sentPercent}%`,
                      backgroundColor: '#5c9eff',
                    }}
                    title={`Sent: ${stats.sent_count} (${sentPercent.toFixed(1)}%)`}
                  />
                  <div
                    className="h-full transition-all"
                    style={{
                      width: `${100 - sentPercent}%`,
                      backgroundColor: '#4caf50',
                    }}
                    title={`Received: ${stats.received_count} (${(100 - sentPercent).toFixed(1)}%)`}
                  />
                </div>
                <div className="flex items-center gap-3 text-[10px] text-gray-500">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: '#5c9eff' }} />
                    Sent
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: '#4caf50' }} />
                    Received
                  </span>
                </div>
              </div>
            </Section>

            {/* Protocol Distribution */}
            <Section title="Protocol Distribution">
              <div className="space-y-1.5">
                {stats.protocols.map((proto) => (
                  <div key={proto.protocol} className="space-y-0.5">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-gray-300 font-medium">{proto.protocol}</span>
                      <span className="text-gray-500">
                        {proto.count} ({proto.percentage.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="h-2 rounded-sm bg-ws-bg border border-ws-border overflow-hidden">
                      <div
                        className="h-full rounded-sm transition-all"
                        style={{
                          width: `${proto.percentage}%`,
                          backgroundColor: getProtocolBarColor(proto.protocol),
                        }}
                      />
                    </div>
                  </div>
                ))}
                {stats.protocols.length === 0 && (
                  <div className="text-[10px] text-gray-500">No protocol data</div>
                )}
              </div>
            </Section>

            {/* Top Connections */}
            {stats.top_connections.length > 0 && (
              <Section title="Top Connections">
                <div className="space-y-1">
                  {stats.top_connections.map((conn, idx) => (
                    <div
                      key={conn.handle}
                      className="flex items-center justify-between text-[11px] px-1.5 py-1 rounded bg-ws-bg/50 border border-ws-border/50"
                    >
                      <span className="text-gray-300 font-mono">
                        <span className="text-gray-500 mr-1">#{idx + 1}</span>
                        {conn.handle}
                      </span>
                      <span className="text-gray-400">{conn.packets} pkts</span>
                    </div>
                  ))}
                </div>
              </Section>
            )}
          </>
        )}
      </div>
    </div>
  );
};

/** Section wrapper with title */
const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="space-y-2">
    <h3 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{title}</h3>
    {children}
  </div>
);

/** Single stat row: label + value */
const StatRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex justify-between items-center text-[11px]">
    <span className="text-gray-400">{label}</span>
    <span className="text-gray-200 font-medium font-mono">{value}</span>
  </div>
);

export default StatsPanel;
