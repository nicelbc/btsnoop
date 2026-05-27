import React, { useState, useCallback, useRef } from 'react';
import { usePacketStore } from '../stores/packetStore';

interface UploadZoneProps {
  onSessionCreated: (sessionId: string) => void;
}

export const UploadZone: React.FC<UploadZoneProps> = ({ onSessionCreated }) => {
  const { dispatch } = usePacketStore();
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCountRef = useRef(0);

  const handleUpload = useCallback(
    async (file: File) => {
      setIsUploading(true);
      setProgress(0);
      setError(null);

      const formData = new FormData();
      formData.append('file', file);

      try {
        const xhr = new XMLHttpRequest();

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            setProgress(Math.round((e.loaded / e.total) * 100));
          }
        };

        const response = await new Promise<{ session_id: string }>((resolve, reject) => {
          xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              try {
                resolve(JSON.parse(xhr.responseText));
              } catch {
                reject(new Error('Invalid response from server'));
              }
            } else {
              reject(new Error(`Upload failed: ${xhr.statusText}`));
            }
          };
          xhr.onerror = () => reject(new Error('Network error'));
          xhr.open('POST', '/api/upload');
          xhr.send(formData);
        });

        dispatch({ type: 'RESET' });
        dispatch({ type: 'SET_SESSION_ID', sessionId: response.session_id });
        onSessionCreated(response.session_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed');
      } finally {
        setIsUploading(false);
      }
    },
    [dispatch, onSessionCreated]
  );

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCountRef.current++;
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCountRef.current--;
    if (dragCountRef.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      dragCountRef.current = 0;

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleUpload(files[0]);
      }
    },
    [handleUpload]
  );

  const handleClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        handleUpload(files[0]);
      }
    },
    [handleUpload]
  );

  return (
    <div
      className={`upload-zone ${isDragging ? 'upload-zone-active' : ''}`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleClick}
    >
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept=".log,.cfa,.btsnoop,.bin"
        onChange={handleFileChange}
      />

      {isUploading ? (
        <div className="space-y-4">
          <div className="text-ws-accent text-lg font-medium">Uploading...</div>
          <div className="w-64 mx-auto bg-ws-bg rounded-full h-2 overflow-hidden">
            <div
              className="bg-ws-accent h-full transition-all duration-300 rounded-full"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="text-gray-500 text-sm">{progress}%</div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="text-5xl opacity-30">
            <svg
              className="w-16 h-16 mx-auto text-gray-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
          </div>
          <div className="text-gray-300 text-lg">
            Drop a btsnoop file here or click to browse
          </div>
          <div className="text-gray-600 text-sm">
            Supports .log, .cfa, .btsnoop, .bin files
          </div>
        </div>
      )}

      {error && (
        <div className="mt-4 text-red-400 text-sm bg-red-900/20 px-4 py-2 rounded">
          {error}
        </div>
      )}
    </div>
  );
};

// Full-screen drop overlay component
export const DropOverlay: React.FC<{
  visible: boolean;
}> = ({ visible }) => {
  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 bg-ws-bg/90 backdrop-blur-sm flex items-center justify-center pointer-events-none">
      <div className="border-2 border-dashed border-ws-accent rounded-2xl p-16 text-center animate-pulse">
        <div className="text-ws-accent text-2xl font-bold mb-2">Drop file to analyze</div>
        <div className="text-gray-400">Release to upload btsnoop file</div>
      </div>
    </div>
  );
};
