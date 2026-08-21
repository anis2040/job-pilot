import type { ResumeTemplate } from '../../api/types';

interface ResumeTemplatePickerProps {
  templates: ResumeTemplate[];
  value: string;
  onChange: (templateId: string) => void;
  disabled?: boolean;
  label?: string;
  showLabel?: boolean;
  className?: string;
}

export function ResumeTemplatePicker({
  templates,
  value,
  onChange,
  disabled = false,
  label = 'Resume template',
  showLabel = false,
  className = '',
}: ResumeTemplatePickerProps) {
  if (templates.length <= 1) return null;

  const classes = ['resume-template-control', showLabel ? 'with-label' : '', className]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes}>
      {showLabel && <span className="resume-template-label">{label}</span>}
      <div className="resume-template-picker" role="radiogroup" aria-label={label}>
        {templates.map(template => {
          const active = value === template.id;
          return (
            <button
              key={template.id}
              type="button"
              className={`template-segment${active ? ' active' : ''}`}
              aria-pressed={active}
              onClick={() => { if (!active) onChange(template.id); }}
              disabled={disabled}
              title={template.supports_profile_image ? 'Supports profile image' : 'No profile image'}
            >
              {template.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
