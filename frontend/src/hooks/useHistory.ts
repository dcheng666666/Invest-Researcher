import { useState, useCallback } from "react";
import type { HistoryItem } from "../types";

const STORAGE_KEY = "analysis_history";
const MAX_ITEMS = 50;

function load(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persist(items: HistoryItem[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

export function useHistory() {
  const [items, setItems] = useState<HistoryItem[]>(load);

  const addItem = useCallback((symbol: string, code: string, name: string) => {
    setItems((prev) => {
      const filtered = prev.filter((it) => it.symbol !== symbol);
      const next: HistoryItem[] = [
        { symbol, code, name, lastVisited: new Date().toISOString() },
        ...filtered,
      ].slice(0, MAX_ITEMS);
      persist(next);
      return next;
    });
  }, []);

  const removeItem = useCallback((symbol: string) => {
    setItems((prev) => {
      const next = prev.filter((it) => it.symbol !== symbol);
      persist(next);
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    persist([]);
    setItems([]);
  }, []);

  return { items, addItem, removeItem, clearAll };
}
