import { useState } from 'react';
import { useToast } from '../../../components/ui/useToast';
import { filtersToKey, type Filters } from '../../../utils/filters';
import { LS_RECENT, LS_SAVED } from '../constants';
import { normalizeFilters, searchLabel } from '../utils/searchFilters';

export function useSavedSearches() {
  const { showToast } = useToast();
  const [savedSearches, setSavedSearches] = useState<Filters[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(LS_SAVED) || '[]').map((item: Partial<Filters>) => normalizeFilters(item));
    } catch {
      return [];
    }
  });
  const [recentSearches, setRecentSearches] = useState<Filters[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(LS_RECENT) || '[]').map((item: Partial<Filters>) => normalizeFilters(item));
    } catch {
      return [];
    }
  });

  const saveSearch = (filters: Filters, hasFilters: boolean) => {
    if (!hasFilters) return;
    const key = filtersToKey(filters);
    const next = [filters, ...savedSearches.filter(s => filtersToKey(s) !== key)].slice(0, 10);
    setSavedSearches(next);
    localStorage.setItem(LS_SAVED, JSON.stringify(next));
    showToast('Search saved ☆');
  };

  const captureRecent = (f: Filters) => {
    if (!f.search && !f.source && !f.sources.length && !f.locations.length && !f.posted && !f.cv && !f.remote.length) return;
    const key = filtersToKey(f);
    const next = [f, ...recentSearches.filter(s => filtersToKey(s) !== key)].slice(0, 5);
    setRecentSearches(next);
    localStorage.setItem(LS_RECENT, JSON.stringify(next));
  };

  const removeSaved = (f: Filters) => {
    const next = savedSearches.filter(s => filtersToKey(s) !== filtersToKey(f));
    setSavedSearches(next);
    localStorage.setItem(LS_SAVED, JSON.stringify(next));
  };

  const isSaved = (filters: Filters, hasFilters: boolean) =>
    hasFilters && savedSearches.some(s => filtersToKey(s) === filtersToKey(filters));

  return {
    savedSearches,
    recentSearches,
    saveSearch,
    captureRecent,
    removeSaved,
    isSaved,
    searchLabel,
    showChips: savedSearches.length > 0 || recentSearches.length > 0,
  };
}
