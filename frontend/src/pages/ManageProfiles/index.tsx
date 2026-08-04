import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useProfile } from '../../hooks/useProfile';
import { profiles as profilesApi } from '../../api/client';
import { useToast } from '../../components/ui/useToast';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { PromptDialog } from '../../components/ui/PromptDialog';
import { Topbar } from '../../components/layout/Topbar';
import { buildBackState } from '../../utils/backNavigation';

export default function ManageProfilesPage() {
  const { profiles, switchProfile, refetch } = useProfile();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<{ slug: string; label: string } | null>(null);
  const backState = buildBackState(location);

  const handleSwitch = async (slug: string) => {
    await switchProfile(slug);
    showToast('Profile switched');
  };

  const handleRename = async (label: string) => {
    if (!renameTarget) return;
    const res = await profilesApi.setLabel(renameTarget.slug, label);
    setRenameTarget(null);
    if (res.ok) { await refetch(); showToast('Renamed'); }
    else showToast('Failed to rename', 'err');
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    const res = await profilesApi.delete(deleteTarget);
    setDeleteTarget(null);
    if (res.ok) { await refetch(); showToast('Profile deleted'); }
    else showToast('Failed to delete', 'err');
  };

  const handleAddNew = async () => {
    const res = await profilesApi.create();
    if (res.ok) { await refetch(); navigate('/setup'); }
  };

  if (profiles.length === 0) {
    return (
      <>
        <Topbar backTo="/" backLabel="Home" title="Manage Profiles" />
        <main className="manage-profiles-page page-enter" id="main-content">
          <div className="empty-state">
            <div className="empty-state-icon">👤</div>
            <div className="empty-state-title">No profiles yet</div>
            <div className="empty-state-desc">Create your first profile to get started.</div>
            <button className="btn btn-primary" style={{ marginTop: 'var(--space-3)' }} onClick={handleAddNew}>
              + Create profile
            </button>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <Topbar backTo="/" backLabel="Home" title="Manage Profiles" />
      <main className="manage-profiles-page" id="main-content">
        <div className="profiles-list">
          {profiles.map(p => (
            <div key={p.slug} className="profile-row" onClick={() => navigate(`/profile-settings/${p.slug}`, { state: backState })}
              style={{ cursor: 'pointer' }}>
              <span className="avatar" style={{ background: p.color }}>{p.initials}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="profile-row-label">{p.label || p.name}</div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-faint)' }}>profiles/{p.slug}/</div>
              </div>
              {p.active && <span className="badge badge-green">Active</span>}
              <div className="profile-row-actions" onClick={e => e.stopPropagation()}>
                {!p.active && (
                  <button className="btn btn-sm btn-ghost" onClick={() => handleSwitch(p.slug)}>Switch</button>
                )}
                <button className="btn btn-sm btn-ghost"
                  onClick={() => setRenameTarget({ slug: p.slug, label: p.label || p.name })}>
                  Rename
                </button>
                <button
                  className="btn btn-sm btn-danger-outline"
                  disabled={p.active || profiles.length <= 1}
                  title={p.active ? 'Switch to another profile first' : profiles.length <= 1 ? 'Cannot delete the only profile' : 'Delete profile'}
                  onClick={() => setDeleteTarget(p.slug)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>

        <button className="btn btn-primary" style={{ marginTop: 'var(--space-4)' }} onClick={handleAddNew}>
          + Add new profile
        </button>

        <PromptDialog
          open={renameTarget !== null}
          title="Rename profile"
          defaultValue={renameTarget?.label ?? ''}
          placeholder="Profile label"
          confirmLabel="Rename"
          onConfirm={handleRename}
          onCancel={() => setRenameTarget(null)}
        />

        <ConfirmDialog
          open={deleteTarget !== null}
          title="Delete profile?"
          message="This will permanently delete the profile and all its job data."
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      </main>
    </>
  );
}
