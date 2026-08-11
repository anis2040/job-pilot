import { StancePicker } from './StancePicker';
import type { BuildCvConfig } from '../../api/types';

interface CvActionBlockProps {
  stance: BuildCvConfig['experience_positioning'];
  onStanceChange: (next: BuildCvConfig['experience_positioning']) => void;
  disabled?: boolean;
  children: React.ReactNode;
}

export function CvActionBlock({ stance, onStanceChange, disabled, children }: CvActionBlockProps) {
  return (
    <div className="cv-action-block">
      <div className="cv-action-block-top">
        <StancePicker value={stance} onChange={onStanceChange} disabled={disabled} />
      </div>
      <div className="cv-action-block-bottom">
        {children}
      </div>
    </div>
  );
}
