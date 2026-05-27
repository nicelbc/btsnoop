import React, { useReducer, useCallback, useRef, useState, useEffect } from 'react';
type LiveState = { sessionId: string; device: string } | null;
import { PacketList } from './components/PacketList';
import { ProtocolTree } from './components/ProtocolTree';
import { HexView } from './components/HexView';
import { UploadZone, DropOverlay } from './components/UploadZone';
import { Toolbar } from './components/Toolbar';
import { FilterBar } from './components/FilterBar';
import { StatusBar } from './components/StatusBar';
import { StatsPanel } from './components/StatsPanel';
import {
  PacketContext,
  packetReducer,
  initialState,
} from './stores/packetStore';
import { WebSocketClient } from './ws/client';

const App: React.FC = () => {
  const [state, dispatch] = useReducer(packetReducer, initialState);
  const wsClientRef = useRef<WebSocketClient | null>(null);
  const [showUpload, setShowUpload] = useState(true);
  const [globalDragging, setGlobalDragging] = useState(false);
  const [liveState, setLiveState] = useState<LiveState>(null);
  const [showStats, setShowStats] = useState(false);
  const dragCountRef = useRef(0);
  const handleOpenFileRef = useRef<(file: File) => void>(() => {});

  // Global drag-and-drop overlay
  useEffect(() => {
    const handleDragEnter = (e: DragEvent) => {
      e.preventDefault();
      dragCountRef.current++;
      if (dragCountRef.current === 1) {
        setGlobalDragging(true);
      }
    };

    const handleDragLeave = (e: DragEvent) => {
      e.preventDefault();
      dragCountRef.current--;
      if (dragCountRef.current === 0) {
        setGlobalDragging(false);
      }
    };

    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
    };

    const handleDrop = (e: DragEvent) => {
      e.preventDefault();
      dragCountRef.current = 0;
      setGlobalDragging(false);
      const files = e.dataTransfer?.files;
      if (files && files.length > 0) {
        handleOpenFileRef.current(files[0]);
      }
    };

    document.addEventListener('dragenter', handleDragEnter);
    document.addEventListener('dragleave', handleDragLeave);
    document.addEventListener('dragover', handleDragOver);
    document.addEventListener('drop', handleDrop);

    return () => {
      document.removeEventListener('dragenter', handleDragEnter);
      document.removeEventListener('dragleave', handleDragLeave);
      document.removeEventListener('dragover', handleDragOver);
      document.removeEventListener('drop', handleDrop);
    };
  }, []);

  // Listen for filter apply events dispatched by FilterBar
  useEffect(() => {
    const handleFilterApply = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (wsClientRef.current && detail) {
        wsClientRef.current.setFilter(detail.filter || '');
      }
    };

    window.addEventListener('btsnoop:apply_filter', handleFilterApply);
    return () => {
      window.removeEventListener('btsnoop:apply_filter', handleFilterApply);
    };
  }, []);

  const handleSessionCreated = useCallback(
    (sessionId: string) => {
      // Disconnect existing WebSocket
      if (wsClientRef.current) {
        wsClientRef.current.disconnect();
      }

      // Create new WebSocket connection
      const client = new WebSocketClient(sessionId, dispatch);
      client.connect();
      wsClientRef.current = client;
      setShowUpload(false);
    },
    [dispatch]
  );

  const handleSelectPacket = useCallback((index: number) => {
    if (wsClientRef.current) {
      wsClientRef.current.requestDetail(index);
    }
  }, []);

  const handleOpenFile = useCallback(
    (file: File) => {
      // Upload the file via the same mechanism as UploadZone
      const formData = new FormData();
      formData.append('file', file);

      fetch('/api/upload', { method: 'POST', body: formData })
        .then((res) => res.json())
        .then((data: { session_id: string }) => {
          dispatch({ type: 'RESET' });
          dispatch({ type: 'SET_SESSION_ID', sessionId: data.session_id });
          handleSessionCreated(data.session_id);
        })
        .catch((err) => {
          console.error('Upload failed:', err);
        });
    },
    [dispatch, handleSessionCreated]
  );
  handleOpenFileRef.current = handleOpenFile;

  const handleNewFile = useCallback(() => {
    if (wsClientRef.current) {
      wsClientRef.current.disconnect();
      wsClientRef.current = null;
    }
    dispatch({ type: 'RESET' });
    setLiveState(null);
    setShowUpload(true);
  }, [dispatch]);

  const handleStartCapture = useCallback(async () => {
    try {
      const res = await fetch('/api/live/start', { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        alert(`启动失败: ${err.detail}`);
        return;
      }
      const data = await res.json();
      dispatch({ type: 'RESET' });
      setLiveState({ sessionId: data.session_id, device: data.device });
      setShowUpload(false);

      // Connect to live WebSocket
      if (wsClientRef.current) wsClientRef.current.disconnect();
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const ws = new WebSocket(`${protocol}//${host}/ws/live/${data.session_id}`);
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'packet_batch') {
          dispatch({ type: 'ADD_PACKETS', packets: msg.packets });
        } else if (msg.type === 'packet_detail') {
          dispatch({ type: 'SET_DETAIL', detail: { packet: msg.packet, raw_hex: msg.raw_hex, flags: msg.flags } });
        } else if (msg.type === 'live_stopped') {
          setLiveState(null);
          dispatch({ type: 'SET_WS_CONNECTED', connected: false });
        }
      };
      ws.onopen = () => dispatch({ type: 'SET_WS_CONNECTED', connected: true });
      ws.onclose = () => dispatch({ type: 'SET_WS_CONNECTED', connected: false });
      dispatch({ type: 'SET_SESSION_ID', sessionId: data.session_id });
    } catch (err) {
      alert(`ADB 连接失败: ${err}`);
    }
  }, [dispatch]);

  const handleStopCapture = useCallback(async () => {
    if (!liveState) return;
    try {
      await fetch(`/api/live/stop/${liveState.sessionId}`, { method: 'POST' });
    } catch (e) {
      console.error('Stop error:', e);
    }
    setLiveState(null);
  }, [liveState]);

  const handleExport = useCallback(() => {
    const sessionId = state.sessionId;
    if (!sessionId) return;
    const format = window.prompt(
      '导出格式:\n1 - pcapng (Wireshark)\n2 - JSON\n3 - CSV\n\n输入数字:',
      '1'
    );
    if (format === '1') window.open(`/api/sessions/${sessionId}/export/pcapng`, '_blank');
    else if (format === '2') window.open(`/api/sessions/${sessionId}/export/json`, '_blank');
    else if (format === '3') window.open(`/api/sessions/${sessionId}/export/csv`, '_blank');
  }, [state.sessionId]);

  return (
    <PacketContext.Provider value={{ state, dispatch }}>
      <div className="h-screen flex flex-col bg-ws-bg">
        {/* Toolbar */}
        <Toolbar
          onOpenFile={handleOpenFile}
          onStartCapture={handleStartCapture}
          onStopCapture={handleStopCapture}
          onExport={handleExport}
          isCapturing={!!liveState}
        />

        {/* Main content */}
        {showUpload ? (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="w-full max-w-lg">
              <UploadZone onSessionCreated={handleSessionCreated} />
            </div>
          </div>
        ) : (
          <>
            {/* Filter Bar */}
            <FilterBar />

            <div className="flex-1 flex flex-col min-h-0">
              {/* Top panel: Packet List */}
              <div className="h-[45%] min-h-0 p-1">
                <PacketList onSelectPacket={handleSelectPacket} />
              </div>

              {/* Resizer bar */}
              <div className="h-1 bg-ws-border cursor-row-resize hover:bg-ws-accent/50 transition-colors shrink-0" />

              {/* Bottom panel: Protocol Tree + Hex View side by side */}
              <div className="flex-1 flex min-h-0 p-1 gap-1">
                {/* Protocol Tree */}
                <div className="w-1/2 min-w-0">
                  <ProtocolTree />
                </div>

                {/* Vertical resizer */}
                <div className="w-1 bg-ws-border cursor-col-resize hover:bg-ws-accent/50 transition-colors shrink-0" />

                {/* Hex View */}
                <div className="w-1/2 min-w-0">
                  <HexView />
                </div>
              </div>
            </div>
          </>
        )}

        {/* Status bar */}
        <StatusBar />

        {/* Stats toggle button (floating) */}
        {!showUpload && (
          <button
            onClick={() => setShowStats((v) => !v)}
            title="Toggle statistics panel"
            className={`fixed bottom-8 right-4 z-40 flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium shadow-lg transition-colors border ${
              showStats
                ? 'bg-ws-accent/20 text-ws-accent border-ws-accent/40'
                : 'bg-ws-panel text-gray-300 border-ws-border hover:bg-ws-hover hover:text-gray-100'
            }`}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Stats
          </button>
        )}

        {/* Stats Panel */}
        <StatsPanel
          sessionId={state.sessionId}
          visible={showStats}
          onClose={() => setShowStats(false)}
        />

        {/* Global drop overlay */}
        <DropOverlay visible={globalDragging && !showUpload} />
      </div>
    </PacketContext.Provider>
  );
};

export default App;
