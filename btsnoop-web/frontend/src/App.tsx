import React, { useReducer, useCallback, useRef, useState, useEffect } from 'react';
type LiveState = { sessionId: string; device: string } | null;
import { PacketList } from './components/PacketList';
import { ProtocolTree } from './components/ProtocolTree';
import { HexView } from './components/HexView';
import { UploadZone, DropOverlay } from './components/UploadZone';
import { Toolbar } from './components/Toolbar';
import { FilterBar } from './components/FilterBar';
import { StatusBar } from './components/StatusBar';
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
  const dragCountRef = useRef(0);

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

  return (
    <PacketContext.Provider value={{ state, dispatch }}>
      <div className="h-screen flex flex-col bg-ws-bg">
        {/* Toolbar */}
        <Toolbar
          onOpenFile={handleOpenFile}
          onStartCapture={handleStartCapture}
          onStopCapture={handleStopCapture}
          onExport={undefined}
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

        {/* Global drop overlay */}
        <DropOverlay visible={globalDragging && !showUpload} />
      </div>
    </PacketContext.Provider>
  );
};

export default App;
