import { BackButton } from './BackButton';
import { ProfileAvatar } from '../ui/ProfileAvatar';

interface TopbarProps {
  backTo: string;
  backLabel?: string;
  title: string;
  avatarColor?: string;
  avatarInitials?: string;
  avatarImageUrl?: string | null;
}

export function Topbar({ backTo, backLabel = 'Back', title, avatarColor, avatarInitials, avatarImageUrl }: TopbarProps) {
  return (
    <div className="topbar">
      <BackButton fallbackTo={backTo} fallbackLabel={backLabel} className="topbar-back" />
      {avatarColor && avatarInitials && (
        <ProfileAvatar
          profile={{ color: avatarColor, initials: avatarInitials, image_url: avatarImageUrl, label: title, name: title }}
          size="topbar"
        />
      )}
      <span className="topbar-title">{title}</span>
    </div>
  );
}
