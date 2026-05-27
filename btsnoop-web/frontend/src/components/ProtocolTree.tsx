import React, { useState, useCallback } from 'react';
import { usePacketStore } from '../stores/packetStore';
import { DecodedLayer, DecodedField } from '../types';

interface TreeNodeState {
  [key: string]: boolean;
}

const ChevronIcon: React.FC<{ expanded: boolean }> = ({ expanded }) => (
  <svg
    className={`w-3 h-3 text-gray-500 transition-transform duration-100 flex-shrink-0 ${
      expanded ? 'rotate-90' : ''
    }`}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
  </svg>
);

interface FieldNodeProps {
  field: DecodedField;
  depth: number;
  path: string;
  expandedNodes: TreeNodeState;
  toggleNode: (path: string) => void;
  onFieldClick: (field: DecodedField) => void;
  highlightedOffset: number | null;
  highlightedLength: number | null;
}

const FieldNode: React.FC<FieldNodeProps> = ({
  field,
  depth,
  path,
  expandedNodes,
  toggleNode,
  onFieldClick,
  highlightedOffset,
  highlightedLength,
}) => {
  const hasChildren = field.children && field.children.length > 0;
  const isExpanded = expandedNodes[path] ?? false;
  const isHighlighted =
    highlightedOffset !== null &&
    highlightedLength !== null &&
    field.offset === highlightedOffset &&
    field.length === highlightedLength;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasChildren) {
      toggleNode(path);
    }
    onFieldClick(field);
  };

  return (
    <>
      <div
        className={`tree-node flex items-center gap-1 group ${
          isHighlighted ? 'bg-blue-900/40 !border-l-2 !border-l-blue-400' : ''
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={handleClick}
        role="treeitem"
        aria-expanded={hasChildren ? isExpanded : undefined}
      >
        {/* Tree connector lines */}
        <span className="flex-shrink-0 w-4 flex items-center justify-center">
          {hasChildren ? (
            <ChevronIcon expanded={isExpanded} />
          ) : (
            <span className="w-1 h-1 rounded-full bg-gray-600" />
          )}
        </span>

        {/* Field name */}
        <span className="text-gray-400">{field.name}</span>
        <span className="text-gray-600 mx-0.5">:</span>

        {/* Field value */}
        <span className="text-gray-200 truncate">{field.value}</span>

        {/* Hex offset info */}
        <span className="ml-auto text-[10px] text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 pl-4 font-mono">
          offset {field.offset}, len {field.length}
        </span>
      </div>
      {hasChildren && isExpanded && (
        <div role="group">
          {field.children!.map((child, idx) => (
            <FieldNode
              key={`${path}.${idx}`}
              field={child}
              depth={depth + 1}
              path={`${path}.${idx}`}
              expandedNodes={expandedNodes}
              toggleNode={toggleNode}
              onFieldClick={onFieldClick}
              highlightedOffset={highlightedOffset}
              highlightedLength={highlightedLength}
            />
          ))}
        </div>
      )}
    </>
  );
};

interface LayerNodeProps {
  layer: DecodedLayer;
  layerIndex: number;
  expandedNodes: TreeNodeState;
  toggleNode: (path: string) => void;
  onFieldClick: (field: DecodedField) => void;
  highlightedOffset: number | null;
  highlightedLength: number | null;
}

const LayerNode: React.FC<LayerNodeProps> = ({
  layer,
  layerIndex,
  expandedNodes,
  toggleNode,
  onFieldClick,
  highlightedOffset,
  highlightedLength,
}) => {
  const path = `layer-${layerIndex}`;
  const isExpanded = expandedNodes[path] ?? true; // Layers expanded by default

  const handleLayerClick = () => {
    toggleNode(path);
  };

  /** Protocol color coding based on protocol name */
  const getProtocolColor = (protocol: string): string => {
    const p = protocol.toLowerCase();
    if (p.includes('hci')) return 'text-yellow-300';
    if (p.includes('l2cap')) return 'text-green-300';
    if (p.includes('att') || p.includes('gatt')) return 'text-cyan-300';
    if (p.includes('smp')) return 'text-pink-300';
    if (p.includes('avdtp') || p.includes('a2dp')) return 'text-orange-300';
    if (p.includes('avctp') || p.includes('avrcp')) return 'text-purple-300';
    if (p.includes('sdp')) return 'text-blue-300';
    if (p.includes('rfcomm')) return 'text-emerald-300';
    return 'text-ws-accent';
  };

  return (
    <div className="border-b border-ws-border/30" role="treeitem" aria-expanded={isExpanded}>
      {/* Layer header */}
      <div
        className="tree-node flex items-center gap-1 bg-ws-header/50 hover:bg-ws-hover cursor-pointer"
        onClick={handleLayerClick}
      >
        <ChevronIcon expanded={isExpanded} />
        <span className={`font-bold ${getProtocolColor(layer.protocol)}`}>
          {layer.protocol}
        </span>
        {layer.summary && (
          <span className="text-gray-400 ml-1.5 truncate font-normal">
            {layer.summary}
          </span>
        )}
        <span className="ml-auto text-[10px] text-gray-600 flex-shrink-0 pl-2 font-mono">
          [{layer.payload_offset}..{layer.payload_offset + layer.payload_length}]
        </span>
      </div>

      {/* Layer fields */}
      {isExpanded && (
        <div className="border-l-2 border-gray-700/50 ml-3" role="group">
          {layer.fields.map((field, idx) => (
            <FieldNode
              key={`${path}.f${idx}`}
              field={field}
              depth={1}
              path={`${path}.f${idx}`}
              expandedNodes={expandedNodes}
              toggleNode={toggleNode}
              onFieldClick={onFieldClick}
              highlightedOffset={highlightedOffset}
              highlightedLength={highlightedLength}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const ProtocolTree: React.FC = () => {
  const { state, dispatch } = usePacketStore();
  const [expandedNodes, setExpandedNodes] = useState<TreeNodeState>({});

  const toggleNode = useCallback((path: string) => {
    setExpandedNodes((prev) => ({
      ...prev,
      [path]: prev[path] === undefined ? false : !prev[path],
    }));
  }, []);

  const handleFieldClick = useCallback(
    (field: DecodedField) => {
      dispatch({
        type: 'SET_HIGHLIGHT_RANGE',
        range: { offset: field.offset, length: field.length },
      });
    },
    [dispatch]
  );

  const expandAll = () => {
    if (!state.selectedDetail) return;
    const newState: TreeNodeState = {};
    state.selectedDetail.packet.layers.forEach((layer: DecodedLayer, li: number) => {
      newState[`layer-${li}`] = true;
      const expandFields = (fields: DecodedField[], prefix: string) => {
        fields.forEach((f, fi) => {
          const key = `${prefix}.f${fi}`;
          if (f.children && f.children.length > 0) {
            newState[key] = true;
            expandFields(f.children, key);
          }
        });
      };
      expandFields(layer.fields, `layer-${li}`);
    });
    setExpandedNodes(newState);
  };

  const collapseAll = () => {
    setExpandedNodes({});
  };

  const { selectedDetail, highlightRange } = state;

  if (!selectedDetail) {
    return (
      <div className="panel h-full flex flex-col">
        <div className="panel-header">
          <span>Protocol Decode</span>
        </div>
        <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
          Select a packet to view protocol details
        </div>
      </div>
    );
  }

  return (
    <div className="panel h-full flex flex-col">
      <div className="panel-header">
        <span>Protocol Decode</span>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500">
            {selectedDetail.packet.layers.length} layer
            {selectedDetail.packet.layers.length !== 1 ? 's' : ''} | #{selectedDetail.packet.index}
          </span>
          <button
            onClick={expandAll}
            className="text-[10px] text-gray-400 hover:text-ws-accent transition-colors"
            title="Expand all"
          >
            [+]
          </button>
          <button
            onClick={collapseAll}
            className="text-[10px] text-gray-400 hover:text-ws-accent transition-colors"
            title="Collapse all"
          >
            [-]
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto font-mono text-xs" role="tree">
        {selectedDetail.packet.layers.map((layer, idx) => (
          <LayerNode
            key={`layer-${idx}`}
            layer={layer}
            layerIndex={idx}
            expandedNodes={expandedNodes}
            toggleNode={toggleNode}
            onFieldClick={handleFieldClick}
            highlightedOffset={highlightRange?.offset ?? null}
            highlightedLength={highlightRange?.length ?? null}
          />
        ))}
      </div>
    </div>
  );
};

export default ProtocolTree;
