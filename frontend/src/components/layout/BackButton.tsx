import type { CSSProperties } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Icon } from '../ui/Icon';
import { getBackFallback, hasPriorHistoryEntry } from '../../utils/backNavigation';

interface BackButtonProps {
  fallbackTo: string;
  fallbackLabel?: string;
  className?: string;
  style?: CSSProperties;
}

export function BackButton({ fallbackTo, fallbackLabel = 'Back', className, style }: BackButtonProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const back = getBackFallback(location.state, fallbackTo, fallbackLabel);

  const handleClick = () => {
    if (hasPriorHistoryEntry(location.key)) {
      navigate(-1);
      return;
    }
    navigate(back.to);
  };

  return (
    <button type="button" className={className} style={style} onClick={handleClick}>
      <Icon name="chevronLeft" size={16} /> {back.label}
    </button>
  );
}
