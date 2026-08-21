import { useEffect, useState } from 'react';
import type { Profile } from '../../api/types';

type AvatarProfile = Pick<Profile, 'initials' | 'color' | 'image_url' | 'label' | 'name'>;
type ProfileAvatarSize = 'sm' | 'base' | 'md' | 'lg' | 'topbar' | 'card';

const SIZE_CLASS: Record<ProfileAvatarSize, string> = {
  sm: 'avatar-sm',
  base: 'avatar',
  md: 'avatar-md',
  lg: 'avatar-lg',
  topbar: 'topbar-avatar',
  card: 'profile-card-avatar',
};

interface ProfileAvatarProps {
  profile: AvatarProfile | null | undefined;
  size?: ProfileAvatarSize;
  className?: string;
}

export function ProfileAvatar({ profile, size = 'base', className = '' }: ProfileAvatarProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageUrl = profile?.image_url || '';

  useEffect(() => {
    setImageFailed(false);
  }, [imageUrl]);

  const showImage = !!imageUrl && !imageFailed;
  const initials = profile?.initials || '?';
  const classes = ['profile-avatar', SIZE_CLASS[size], showImage ? 'has-image' : '', className]
    .filter(Boolean)
    .join(' ');

  return (
    <span
      className={classes}
      style={{ background: profile?.color || '#3b82f6' }}
      aria-hidden="true"
    >
      {showImage ? <img src={imageUrl} alt="" onError={() => setImageFailed(true)} /> : initials}
    </span>
  );
}
