import { useContext, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useProfile } from '../../hooks/useProfile';
import { AuthContext } from '../../hooks/authContext';
import { profiles as profilesApi } from '../../api/client';
import { useClickOutside } from '../../hooks/useFocusTrap';
import { markProfileNeedsFetch } from '../../hooks/profileFetchSignal';
import { Icon } from '../ui/Icon';
import { ProfileAvatar } from '../ui/ProfileAvatar';
import { buildBackState } from '../../utils/backNavigation';

export function ProfileDropdown() {
  const { active, profiles, switchProfile, refetch } = useProfile();
  const auth = useContext(AuthContext);
  const user = auth?.user ?? null;
  const logout = auth?.logout;
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const backState = buildBackState(location);

  useClickOutside(ref, () => setOpen(false), open);

  const handleSwitch = async (slug: string) => {
    setOpen(false);
    const { empty } = await switchProfile(slug);
    // Empty profile → signal the dashboard to auto-fetch jobs (matches old /?fetch=1).
    if (empty) markProfileNeedsFetch();
  };

  const handleAddNew = async () => {
    setOpen(false);
    const { ok } = await profilesApi.create();
    if (ok) { await refetch(); navigate('/setup'); }
  };

  const handleMenuKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setOpen(false); return; }
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const items = menuRef.current?.querySelectorAll<HTMLElement>('button, a');
    if (!items?.length) return;
    const arr = Array.from(items);
    const idx = arr.indexOf(document.activeElement as HTMLElement);
    const next = e.key === 'ArrowDown' ? arr[(idx + 1) % arr.length] : arr[(idx - 1 + arr.length) % arr.length];
    next?.focus();
  };

  if (!active) return null;

  return (
    <div ref={ref} className="profile-dropdown">
      <button
        className="avatar-btn"
        aria-label="Profile menu"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen(o => !o)}
      >
        <ProfileAvatar profile={active} />
      </button>

      {open && (
        <div ref={menuRef} className="profile-menu open" role="menu" onKeyDown={handleMenuKeyDown}>
          {/* Active profile header */}
          <div className="profile-menu-active">
            <ProfileAvatar profile={active} size="md" />
            <div className="profile-menu-active-info">
              <span className="profile-menu-active-name">{active.label || active.name}</span>
              <span className="profile-menu-active-sub">Active profile</span>
            </div>
          </div>

          {/* Other profiles */}
          {profiles.filter(p => !p.active).length > 0 && (
            <>
              <div className="profile-menu-section-label">Switch to</div>
              {profiles.filter(p => !p.active).map(p => (
                <button key={p.slug} role="menuitem" className="profile-menu-item" onClick={() => handleSwitch(p.slug)}>
                  <ProfileAvatar profile={p} size="sm" />
                  <span>{p.label || p.name}</span>
                </button>
              ))}
            </>
          )}

          <div className="profile-menu-divider" />

          <button role="menuitem" className="profile-menu-item" onClick={handleAddNew}>
            <Icon name="plus" size={14} />
            <span>Add new profile</span>
          </button>
          <Link role="menuitem" to="/manage-profiles" state={backState} className="profile-menu-item" onClick={() => setOpen(false)}>
            <Icon name="user" size={14} />
            <span>Manage profiles</span>
          </Link>

          {user && !user.auth_disabled && logout && (
            <>
              <div className="profile-menu-divider" />
              {user.email && (
                <div className="profile-menu-section-label">{user.email}</div>
              )}
              <button
                role="menuitem"
                className="profile-menu-item"
                onClick={() => { setOpen(false); void logout(); }}
              >
                <Icon name="logOut" size={14} />
                <span>Sign out</span>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
