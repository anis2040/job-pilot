import type { BuildCvConfig } from '../../api/types';

const OPTIONS: {
  value: BuildCvConfig['experience_positioning'];
  label: string;
  icon: string;
  hint: string;
}[] = [
  { value: 'conservative', label: 'Conservative', icon: '🛡️',
    hint: 'Only what your profile states directly — no reframing.' },
  { value: 'balanced',     label: 'Balanced',     icon: '⚖️',
    hint: 'Direct experience plus genuine transferable skills.' },
  { value: 'aggressive',   label: 'Strong Match',  icon: '🚀',
    hint: "Reaches furthest — mirrors the employer's vocabulary to maximise fit." },
];

interface StancePickerProps {
  value: BuildCvConfig['experience_positioning'];
  onChange: (next: BuildCvConfig['experience_positioning']) => void;
  disabled?: boolean;
}

export function StancePicker({ value, onChange, disabled }: StancePickerProps) {
  const active = OPTIONS.find(o => o.value === value) ?? OPTIONS[1];
  return (
    <div className="stance-control">
      <div className="stance-control-header">
        <span className="stance-control-label">CV positioning</span>
        <span className="stance-control-hint">{active.hint}</span>
      </div>
      <div className="stance-seg" role="group" aria-label="CV positioning stance">
        {OPTIONS.map(opt => (
          <button
            key={opt.value}
            type="button"
            className={`stance-seg-btn${value === opt.value ? ' active' : ''}`}
            onClick={() => { if (value !== opt.value) onChange(opt.value); }}
            disabled={disabled}
            aria-pressed={value === opt.value}
            title={opt.hint}
          >
            <span aria-hidden="true">{opt.icon}</span>
            <span>{opt.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
