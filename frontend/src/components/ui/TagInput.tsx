import { useState, useRef, useId } from 'react';

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  className?: string;
}

export function TagInput({ value, onChange, placeholder, className }: TagInputProps) {
  const [input, setInput] = useState('');
  const inputId = useId();
  const wrapRef = useRef<HTMLDivElement>(null);

  const addTag = (raw: string) => {
    const tag = raw.trim().toLowerCase().replace(/,$/, '');
    if (!tag || value.includes(tag)) return;
    onChange([...value, tag]);
    setInput('');
  };

  const removeTag = (tag: string) => onChange(value.filter(t => t !== tag));

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(input);
    } else if (e.key === 'Backspace' && !input && value.length) {
      removeTag(value[value.length - 1]);
    }
  };

  return (
    <div
      ref={wrapRef}
      className={`tag-wrap${className ? ` ${className}` : ''}`}
      onClick={() => document.getElementById(inputId)?.focus()}
    >
      {value.map(tag => (
        <span key={tag} className="tag" data-value={tag}>
          {tag}
          <button
            type="button"
            onClick={e => { e.stopPropagation(); removeTag(tag); }}
            aria-label={`Remove ${tag}`}
          >
            ✕
          </button>
        </span>
      ))}
      <input
        id={inputId}
        type="text"
        className="tag-input"
        value={input}
        placeholder={value.length === 0 ? placeholder : ''}
        onChange={e => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => { if (input.trim()) addTag(input); }}
      />
    </div>
  );
}
