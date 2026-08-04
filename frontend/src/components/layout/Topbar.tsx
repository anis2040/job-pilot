import { BackButton } from './BackButton';

interface TopbarProps {
  backTo: string;
  backLabel?: string;
  title: string;
  avatarColor?: string;
  avatarInitials?: string;
}

export function Topbar({ backTo, backLabel = 'Back', title, avatarColor, avatarInitials }: TopbarProps) {
  return (
    <div className="topbar">
      <BackButton fallbackTo={backTo} fallbackLabel={backLabel} className="topbar-back" />
      {avatarColor && avatarInitials && (
        <div className="topbar-avatar" style={{ background: avatarColor }}>
          {avatarInitials}
        </div>
      )}
      <span className="topbar-title">{title}</span>
    </div>
  );
}
