import React, { useState, useCallback, useRef, useEffect } from 'react';

interface ResizablePanelProps {
  direction: 'horizontal' | 'vertical';
  initialRatio?: number;
  minRatio?: number;
  maxRatio?: number;
  first: React.ReactNode;
  second: React.ReactNode;
  className?: string;
}

export const ResizablePanel: React.FC<ResizablePanelProps> = ({
  direction,
  initialRatio = 0.5,
  minRatio = 0.15,
  maxRatio = 0.85,
  first,
  second,
  className = '',
}) => {
  const [ratio, setRatio] = useState(initialRatio);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
  }, [direction]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      let newRatio: number;
      if (direction === 'horizontal') {
        newRatio = (e.clientX - rect.left) / rect.width;
      } else {
        newRatio = (e.clientY - rect.top) / rect.height;
      }
      newRatio = Math.max(minRatio, Math.min(maxRatio, newRatio));
      setRatio(newRatio);
    };

    const handleMouseUp = () => {
      if (isDragging.current) {
        isDragging.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [direction, minRatio, maxRatio]);

  const isHorizontal = direction === 'horizontal';
  const firstStyle = isHorizontal
    ? { width: `${ratio * 100}%` }
    : { height: `${ratio * 100}%` };
  const secondStyle = isHorizontal
    ? { width: `${(1 - ratio) * 100}%` }
    : { height: `${(1 - ratio) * 100}%` };

  return (
    <div
      ref={containerRef}
      className={`flex ${isHorizontal ? 'flex-row' : 'flex-col'} ${className}`}
    >
      <div className="min-w-0 min-h-0 overflow-hidden" style={firstStyle}>
        {first}
      </div>
      <div
        className={`shrink-0 ${
          isHorizontal
            ? 'w-1.5 cursor-col-resize hover:bg-ws-accent/60 active:bg-ws-accent'
            : 'h-1.5 cursor-row-resize hover:bg-ws-accent/60 active:bg-ws-accent'
        } bg-ws-border transition-colors`}
        onMouseDown={handleMouseDown}
      />
      <div className="min-w-0 min-h-0 overflow-hidden" style={secondStyle}>
        {second}
      </div>
    </div>
  );
};
