import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoadErrorState } from '@/components/ui/LoadErrorState';

describe('LoadErrorState', () => {
  it('renders title and default description', () => {
    render(<LoadErrorState title="Couldn't load jobs" onRetry={vi.fn()} />);

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText("Couldn't load jobs")).toBeInTheDocument();
    expect(screen.getByText('Something went wrong reaching the server.')).toBeInTheDocument();
  });

  it('renders custom description, icon, and className', () => {
    render(
      <LoadErrorState
        title="Couldn't load AI settings"
        description="Check your connection and try again."
        icon="🔌"
        className="page-error"
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText("Couldn't load AI settings")).toBeInTheDocument();
    expect(screen.getByText('Check your connection and try again.')).toBeInTheDocument();
    expect(screen.getByText('🔌')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveClass('empty-state', 'page-error');
  });

  it('calls onRetry when Retry is clicked', async () => {
    const onRetry = vi.fn();
    render(<LoadErrorState title="Couldn't load jobs" onRetry={onRetry} />);

    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
