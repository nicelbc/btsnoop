import React, { useRef } from 'react';
import { usePacketStore } from '../stores/packetStore';

interface ToolbarProps {
  /** Callback to trigger live capture start */
  onStartCapture?: () => void;
  /** Callback to trigger live capture stop */
  onStopCapture?: () => void;
  /** Callback when a file is selected for import */
  onOpenFile?: (file: File) => void;
  /** Callback to export current packets */
  onExport?: () => void;
  /** Whether live capture is currently active */
  isCapturing?: boolean;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  onStartCapture,
  onStopCapture,
  onOpenFile,
  onExport,
  isCapturing = false,
}) => {
  const { state, dispatch } = usePacketStore();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onOpenFile) {
      onOpenFile(file);
      // Store file name for StatusBar
      sessionStorage.setItem('btsnoop_loaded_file', file.name);
    }
    // Reset input so the same file can be re-selected
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleClear = () => {
    dispatch({ type: 'RESET' });
    sessionStorage.removeItem('btsnoop_loaded_file');
  };

  const handleScrollToBottom = () => {
    window.dispatchEvent(new CustomEvent('btsnoop:scroll_to_bottom'));
  };

  const toggleAutoScroll = () => {
    dispatch({ type: 'SET_AUTO_SCROLL', enabled: !state.autoScroll });
  };

  return (
    <div className="h-9 min-h-[36px] bg-ws-header border-b border-ws-border flex items-center px-2 gap-1.5 select-none">
      {/* Start Capture */}
      <ToolbarButton
        onClick={onStartCapture}
        disabled={isCapturing || !state.wsConnected}
        title="Start live capture"
        active={false}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <span>Start</span>
      </ToolbarButton>

      {/* Stop Capture */}
      <ToolbarButton
        onClick={onStopCapture}
        disabled={!isCapturing}
        title="Stop live capture"
        active={false}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"
          />
        </svg>
        <span>Stop</span>
      </ToolbarButton>

      {/* Separator */}
      <ToolbarSeparator />

      {/* Open File */}
      <ToolbarButton
        onClick={() => fileInputRef.current?.click()}
        title="Open btsnoop file"
        active={false}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z"
          />
        </svg>
        <span>Open</span>
      </ToolbarButton>
      <input
        ref={fileInputRef}
        type="file"
        accept=".log,.btsnoop,.bin,.cfa,.hci"
        onChange={handleFileChange}
        className="hidden"
      />

      {/* Separator */}
      <ToolbarSeparator />

      {/* Clear */}
      <ToolbarButton
        onClick={handleClear}
        disabled={state.packets.length === 0}
        title="Clear all packets"
        active={false}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
          />
        </svg>
        <span>Clear</span>
      </ToolbarButton>

      {/* Scroll to Bottom */}
      <ToolbarButton
        onClick={handleScrollToBottom}
        title="Scroll to bottom"
        active={false}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 14l-7 7m0 0l-7-7m7 7V3"
          />
        </svg>
      </ToolbarButton>

      {/* Auto-scroll Toggle */}
      <ToolbarButton
        onClick={toggleAutoScroll}
        title={state.autoScroll ? 'Disable auto-scroll' : 'Enable auto-scroll'}
        active={state.autoScroll}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
          />
        </svg>
        <span className="text-[10px]">Auto</span>
      </ToolbarButton>

      {/* Separator */}
      <ToolbarSeparator />

      {/* Export */}
      <ToolbarButton
        onClick={onExport}
        disabled={state.packets.length === 0}
        title="Export packets"
        active={false}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <span>Export</span>
      </ToolbarButton>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Connection indicator */}
      <div className="flex items-center gap-1.5 px-2 text-[11px]">
        <span
          className={`status-dot ${
            state.wsConnected ? 'status-connected' : 'status-disconnected'
          }`}
        />
        <span
          className={`${
            state.wsConnected ? 'text-green-400' : 'text-red-400'
          }`}
        >
          {state.wsConnected ? 'Live' : 'Offline'}
        </span>
      </div>
    </div>
  );
};

/** Reusable toolbar button component */
const ToolbarButton: React.FC<{
  onClick?: () => void;
  disabled?: boolean;
  title?: string;
  active: boolean;
  children: React.ReactNode;
}> = ({ onClick, disabled = false, title, active, children }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    title={title}
    className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
      active
        ? 'bg-ws-accent/20 text-ws-accent border border-ws-accent/30'
        : disabled
        ? 'text-gray-600 cursor-not-allowed'
        : 'text-gray-300 hover:bg-ws-hover hover:text-gray-100 border border-transparent'
    }`}
  >
    {children}
  </button>
);

/** Visual separator between button groups */
const ToolbarSeparator: React.FC = () => (
  <div className="w-px h-5 bg-ws-border/60 mx-1" />
);

export default Toolbar;
