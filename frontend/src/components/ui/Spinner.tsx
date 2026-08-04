interface SpinnerProps {
  className?: string;
  size?: 'sm' | 'md';
}

export function Spinner({ className, size = 'md' }: SpinnerProps) {
  return (
    <span
      className={`spinner${size === 'sm' ? ' spinner-sm' : ''}${className ? ` ${className}` : ''}`}
      aria-hidden="true"
    />
  );
}
