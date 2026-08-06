import { useState, useEffect, useRef } from 'react';
import { config as configApi } from '../../../api/client';
import { useFocusTrap } from '../../../hooks/useFocusTrap';
import { useToast } from '../../../components/ui/useToast';
import { Icon } from '../../../components/ui/Icon';
import { TagInput } from '../../../components/ui/TagInput';
import { SearchRow } from '../../../components/ui/SearchRow';
import { createSearchRow, deriveTitleFilters, groupSearchEntries, expandSearchRows, type SearchRowEntry } from '../../../components/ui/searchRowModel';
import type { SearchConfig, SaveConfigResult } from '../../../api/types';

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: (rows: SearchRowEntry[], result: SaveConfigResult) => void;
  allSources: string[];
}

export function SettingsModal({ open, onClose, onSaved, allSources }: SettingsModalProps) {
  const { showToast } = useToast();
  const [cfg, setCfg] = useState<SearchConfig>({ searches: [], title_filter: [], blacklist: [], company_blacklist: [] });
  const [rows, setRows] = useState<SearchRowEntry[]>([]);
  const [saving, setSaving] = useState(false);
  const backdropRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  useFocusTrap(modalRef, open, onClose);

  useEffect(() => {
    if (open) {
      configApi.get()
        .then(data => {
          setCfg(data);
          setRows(groupSearchEntries(data.searches || []));
        })
        .catch(() => showToast('Could not load settings', 'err'));
    }
  }, [open, showToast]);

  const handleSave = async () => {
    const searches = expandSearchRows(rows);
    if (!searches.length) {
      showToast('Add at least one search source', 'err');
      return;
    }
    const next = { ...cfg, searches, title_filter: deriveTitleFilters(rows) };
    setSaving(true);
    try {
      const result = await configApi.save(next);
      showToast(result.fetch_required ? 'Settings saved. Fetching uncovered searches…' : 'Settings saved. Updated local filters.');
      onClose();
      onSaved(rows, result);
    } catch {
      showToast('Could not save settings', 'err');
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div
      ref={backdropRef}
      className="modal-backdrop open"
      onClick={e => { if (e.target === backdropRef.current) onClose(); }}
    >
      <div
        className="modal"
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="fetch-settings-title"
      >
        <div className="modal-header">
          <h2 id="fetch-settings-title">⚙ Fetch Settings</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close"><Icon name="x" size={18} /></button>
        </div>
        <div className="modal-body">
          <p className="settings-intro">Controls what gets scraped from job boards.</p>
          <div className="settings-section">
            <h3>Search Sources</h3>
            {rows.map((row, i) => (
              <SearchRow key={i} entry={row} sources={allSources}
                onChange={v => { const n = [...rows]; n[i] = v; setRows(n); }}
                onRemove={() => setRows(rows.filter((_, j) => j !== i))}
              />
            ))}
            <button className="btn-add" onClick={() => setRows([...rows, createSearchRow(allSources)])}>+ Add search</button>
          </div>
          <div className="settings-section">
            <h3>Exclude keywords <small>(drop jobs containing these words)</small></h3>
            <TagInput value={cfg.blacklist} onChange={v => setCfg(c => ({ ...c, blacklist: v }))} placeholder="add keyword, Enter" />
          </div>
          <div className="settings-section">
            <h3>Exclude companies</h3>
            <TagInput value={cfg.company_blacklist} onChange={v => setCfg(c => ({ ...c, company_blacklist: v }))} placeholder="add company, Enter" />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save settings'}</button>
        </div>
      </div>
    </div>
  );
}
