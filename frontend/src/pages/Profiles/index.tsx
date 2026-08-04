import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProfile } from '../../hooks/useProfile';
import { profiles as profilesApi } from '../../api/client';

export default function ProfilesPage() {
  const { profiles, switchProfile, loading, refetch } = useProfile();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && profiles.length === 0) navigate('/setup');
  }, [loading, profiles, navigate]);

  const handleSelect = async (slug: string) => {
    await switchProfile(slug);
    navigate('/');
  };

  const handleAddNew = async () => {
    const { ok } = await profilesApi.create();
    if (ok) { await refetch(); navigate('/setup'); }
  };

  if (loading) return <div className="page-loading"><span className="spinner" /></div>;

  return (
    <main className="profiles-page page-enter" id="main-content">
      <h1>Choose a profile</h1>
      <div className="profiles-grid">
        {profiles.map(p => (
          <button
            key={p.slug}
            className={`profile-card${p.active ? ' active' : ''}`}
            onClick={() => handleSelect(p.slug)}
          >
            <span className="profile-card-avatar" style={{ background: p.color }}>
              {p.initials}
            </span>
            <span className="profile-card-label">{p.label || p.name}</span>
          </button>
        ))}
        <button className="profile-card add-card" onClick={handleAddNew}>
          <span className="add-icon">+</span>
          <span className="profile-card-label">Add profile</span>
        </button>
      </div>
    </main>
  );
}
