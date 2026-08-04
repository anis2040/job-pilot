import { Link } from 'react-router-dom';
import { Icon } from '../ui/Icon';

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
      <Link to={backTo} className="topbar-back">
        <Icon name="chevronLeft" size={16} /> {backLabel}
      </Link>
      {avatarColor && avatarInitials && (
        <div className="topbar-avatar" style={{ background: avatarColor }}>
          {avatarInitials}
        </div>
      )}
      <span className="topbar-title">{title}</span>
    </div>
  );
}
