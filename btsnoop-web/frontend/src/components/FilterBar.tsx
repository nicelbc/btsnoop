import React, { useState, useRef, useEffect, useCallback } from 'react';
import { usePacketStore } from '../stores/packetStore';

const KNOWN_FIELDS = [
  'hci.type',
  'hci.opcode',
  'l2cap.cid',
  'l2cap.psm',
  'att.opcode',
  'avdtp.signal',
  'direction',
  'protocol',
  'index',
  'bt.addr',
];

const OPERATORS = ['==', '!=', '>=', '<=', '>', '<', 'contains', 'matches'];
const LOGIC_OPS = ['&&', '||', '!'];

const FILTER_HISTORY_KEY = 'btsnoop_filter_history';
const MAX_HISTORY = 10;

function getFilterHistory(): string[] {
  try {
    const raw = localStorage.getItem(FILTER_HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveFilterHistory(history: string[]) {
  localStorage.setItem(FILTER_HISTORY_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)));
}

function addToHistory(filter: string) {
  if (!filter.trim()) return;
  const history = getFilterHistory().filter((h) => h !== filter);
  history.unshift(filter);
  saveFilterHistory(history);
}

/** Basic syntax validation for filter expressions */
function validateFilter(expr: string): boolean {
  if (!expr.trim()) return true; // empty is valid (no filter)
  try {
    // Check balanced parentheses
    let depth = 0;
    for (const ch of expr) {
      if (ch === '(') depth++;
      if (ch === ')') depth--;
      if (depth < 0) return false;
    }
    if (depth !== 0) return false;

    // Check that it has at least one valid field reference or looks syntactically reasonable
    const tokens = expr.trim().split(/\s+/);
    if (tokens.length === 0) return false;

    // Reject trailing/leading logical operators
    const first = tokens[0];
    const last = tokens[tokens.length - 1];
    if (['&&', '||'].includes(first) || ['&&', '||'].includes(last)) return false;

    // Must contain at least one known field or a field-like identifier
    const hasField = tokens.some(
      (t) => KNOWN_FIELDS.includes(t) || /^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$/i.test(t)
    );
    if (!hasField) return false;

    return true;
  } catch {
    return false;
  }
}

interface SuggestionItem {
  value: string;
  type: 'field' | 'operator' | 'history';
}

export const FilterBar: React.FC = () => {
  const { state, dispatch } = usePacketStore();
  const [inputValue, setInputValue] = useState(state.filter);
  const [isValid, setIsValid] = useState(true);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [selectedSuggestion, setSelectedSuggestion] = useState(-1);
  const [showHistory, setShowHistory] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  // Validate on input change
  useEffect(() => {
    if (inputValue.trim() === '') {
      setIsValid(true);
    } else {
      setIsValid(validateFilter(inputValue));
    }
  }, [inputValue]);

  // Close suggestions on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
        setShowHistory(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const computeSuggestions = useCallback(
    (value: string) => {
      const tokens = value.split(/\s+/);
      const lastToken = tokens[tokens.length - 1] || '';
      const items: SuggestionItem[] = [];

      if (!lastToken) {
        // After a space, suggest fields or logic operators
        const prevToken = tokens.length >= 2 ? tokens[tokens.length - 2] : '';
        if (OPERATORS.includes(prevToken) || !prevToken) {
          KNOWN_FIELDS.forEach((f) => items.push({ value: f, type: 'field' }));
        } else if (KNOWN_FIELDS.includes(prevToken) || /\.[a-z]/i.test(prevToken)) {
          OPERATORS.forEach((o) => items.push({ value: o, type: 'operator' }));
        } else {
          LOGIC_OPS.forEach((o) => items.push({ value: o, type: 'operator' }));
          KNOWN_FIELDS.forEach((f) => items.push({ value: f, type: 'field' }));
        }
      } else {
        // Filter fields matching the partial token
        const lower = lastToken.toLowerCase();
        KNOWN_FIELDS.filter((f) => f.toLowerCase().startsWith(lower)).forEach((f) =>
          items.push({ value: f, type: 'field' })
        );
        OPERATORS.filter((o) => o.startsWith(lower)).forEach((o) =>
          items.push({ value: o, type: 'operator' })
        );
      }

      return items.slice(0, 12);
    },
    []
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInputValue(value);

    if (value.trim()) {
      const items = computeSuggestions(value);
      setSuggestions(items);
      setShowSuggestions(items.length > 0);
      setShowHistory(false);
    } else {
      setShowSuggestions(false);
    }
    setSelectedSuggestion(-1);
  };

  const handleFocus = () => {
    if (!inputValue.trim()) {
      const history = getFilterHistory();
      if (history.length > 0) {
        setSuggestions(history.map((h) => ({ value: h, type: 'history' as const })));
        setShowHistory(true);
        setShowSuggestions(true);
      }
    } else {
      const items = computeSuggestions(inputValue);
      setSuggestions(items);
      setShowSuggestions(items.length > 0);
    }
  };

  const applySuggestion = (item: SuggestionItem) => {
    if (item.type === 'history') {
      setInputValue(item.value);
    } else {
      const tokens = inputValue.split(/\s+/);
      tokens[tokens.length - 1] = item.value;
      setInputValue(tokens.join(' ') + ' ');
    }
    setShowSuggestions(false);
    setSelectedSuggestion(-1);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (showSuggestions && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedSuggestion((prev) => Math.min(prev + 1, suggestions.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedSuggestion((prev) => Math.max(prev - 1, -1));
      } else if (e.key === 'Enter' && selectedSuggestion >= 0) {
        e.preventDefault();
        applySuggestion(suggestions[selectedSuggestion]);
        return;
      } else if (e.key === 'Escape') {
        setShowSuggestions(false);
        setSelectedSuggestion(-1);
        return;
      }
    }

    if (e.key === 'Enter' && selectedSuggestion < 0) {
      e.preventDefault();
      applyFilter();
    }
  };

  const applyFilter = () => {
    const trimmed = inputValue.trim();
    if (trimmed && !isValid) return;

    dispatch({ type: 'SET_FILTER', filter: trimmed });

    // Send to backend
    if (state.wsConnected) {
      // The parent component that manages the WS connection should listen for filter changes
      // and send the command. We dispatch a custom event as well for direct WS integration.
      window.dispatchEvent(
        new CustomEvent('btsnoop:apply_filter', { detail: { filter: trimmed } })
      );
    }

    if (trimmed) {
      addToHistory(trimmed);
    }
    setShowSuggestions(false);
  };

  const clearFilter = () => {
    setInputValue('');
    dispatch({ type: 'SET_FILTER', filter: '' });
    if (state.wsConnected) {
      window.dispatchEvent(
        new CustomEvent('btsnoop:apply_filter', { detail: { filter: '' } })
      );
    }
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  const getBorderColor = () => {
    if (!inputValue.trim()) return 'border-ws-border';
    return isValid ? 'border-green-600' : 'border-red-600';
  };

  const getBgColor = () => {
    if (!inputValue.trim()) return 'bg-ws-panel';
    return isValid ? 'bg-green-950/40' : 'bg-red-950/40';
  };

  return (
    <div className="relative w-full px-2 py-1.5 bg-ws-header border-b border-ws-border">
      <div className="flex items-center gap-2">
        {/* Filter icon */}
        <svg
          className="w-4 h-4 text-gray-400 flex-shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
          />
        </svg>

        {/* Input */}
        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={handleInputChange}
            onFocus={handleFocus}
            onKeyDown={handleKeyDown}
            placeholder='Filter: e.g. hci.type == command && direction == sent'
            className={`w-full px-3 py-1.5 text-sm font-mono rounded border ${getBorderColor()} ${getBgColor()} text-gray-100 placeholder-gray-500 outline-none focus:ring-1 focus:ring-ws-accent/50 transition-colors`}
            spellCheck={false}
            autoComplete="off"
          />

          {/* Suggestions dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <div
              ref={suggestionsRef}
              className="absolute top-full left-0 right-0 mt-1 bg-ws-panel border border-ws-border rounded shadow-xl z-50 max-h-60 overflow-y-auto"
            >
              {showHistory && (
                <div className="px-3 py-1 text-[10px] uppercase tracking-wider text-gray-500 border-b border-ws-border/50">
                  Recent Filters
                </div>
              )}
              {suggestions.map((item, idx) => (
                <div
                  key={`${item.value}-${idx}`}
                  className={`px-3 py-1.5 text-sm font-mono cursor-pointer flex items-center gap-2 ${
                    idx === selectedSuggestion
                      ? 'bg-ws-selected text-white'
                      : 'text-gray-300 hover:bg-ws-hover'
                  }`}
                  onClick={() => applySuggestion(item)}
                  onMouseEnter={() => setSelectedSuggestion(idx)}
                >
                  {item.type === 'field' && (
                    <span className="text-[10px] px-1 py-0.5 bg-blue-900/50 text-blue-300 rounded">
                      field
                    </span>
                  )}
                  {item.type === 'operator' && (
                    <span className="text-[10px] px-1 py-0.5 bg-purple-900/50 text-purple-300 rounded">
                      op
                    </span>
                  )}
                  {item.type === 'history' && (
                    <svg className="w-3 h-3 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  )}
                  <span>{item.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Apply button */}
        <button
          onClick={applyFilter}
          disabled={!isValid && inputValue.trim() !== ''}
          className={`px-3 py-1.5 text-xs font-semibold rounded transition-colors ${
            isValid
              ? 'bg-ws-accent/20 text-ws-accent border border-ws-accent/40 hover:bg-ws-accent/30'
              : 'bg-gray-700/50 text-gray-500 border border-gray-700 cursor-not-allowed'
          }`}
        >
          Apply
        </button>

        {/* Clear button */}
        <button
          onClick={clearFilter}
          className="px-3 py-1.5 text-xs font-semibold rounded bg-gray-700/50 text-gray-300 border border-gray-600/50 hover:bg-gray-600/50 hover:text-gray-200 transition-colors"
        >
          Clear
        </button>
      </div>
    </div>
  );
};

export default FilterBar;
