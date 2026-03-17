"use client";
import { useState, useCallback, useEffect } from "react";
import type { ClosingRankRow } from "@/lib/api";

const LS_KEY = "neetpg_favorites_v1";

export type FavoriteMap = Map<string, ClosingRankRow>;

/** Derive a stable unique key for a row (round-agnostic) */
export function rowKey(row: ClosingRankRow): string {
  return [
    row.year,
    row.counselling_type,
    row.counselling_state ?? "",
    row.institute_name ?? "",
    row.institute_pincode ?? "",
    row.course_norm ?? "",
    row.quota_norm ?? "",
    row.allotted_category_norm ?? "",
  ].join("|");
}

function load(): FavoriteMap {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return new Map();
    const obj: Record<string, ClosingRankRow> = JSON.parse(raw);
    return new Map(Object.entries(obj));
  } catch {
    return new Map();
  }
}

function save(map: FavoriteMap) {
  const obj: Record<string, ClosingRankRow> = {};
  map.forEach((v, k) => { obj[k] = v; });
  localStorage.setItem(LS_KEY, JSON.stringify(obj));
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<FavoriteMap>(() => new Map());

  // Hydrate from localStorage only on client
  useEffect(() => {
    setFavorites(load());
  }, []);

  const toggleFavorite = useCallback((row: ClosingRankRow) => {
    const key = rowKey(row);
    setFavorites(prev => {
      const next = new Map(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.set(key, row);
      }
      save(next);
      return next;
    });
  }, []);

  const isFavorite = useCallback(
    (row: ClosingRankRow) => favorites.has(rowKey(row)),
    [favorites]
  );

  const clearFavorites = useCallback(() => {
    setFavorites(new Map());
    localStorage.removeItem(LS_KEY);
  }, []);

  return { favorites, toggleFavorite, isFavorite, clearFavorites };
}
