/**
 * Dialog tests — behaviour-first.
 *
 * Tests verify that dialogs appear, accept input, and fire the right callbacks
 * based on user actions.  Visual/CSS details are omitted.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { PromptDialog } from '@/components/ui/PromptDialog'

// ── ConfirmDialog ─────────────────────────────────────────────────────────────

describe('ConfirmDialog', () => {
  it('is not in the DOM when closed', () => {
    render(<ConfirmDialog open={false} title="Delete?" onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('shows title and optional message when open', () => {
    render(<ConfirmDialog open title="Are you sure?" message="This cannot be undone." onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByText('Are you sure?')).toBeInTheDocument()
    expect(screen.getByText('This cannot be undone.')).toBeInTheDocument()
  })

  it('confirm button triggers onConfirm', async () => {
    const onConfirm = vi.fn()
    render(<ConfirmDialog open title="Delete?" confirmLabel="Yes, delete" onConfirm={onConfirm} onCancel={vi.fn()} />)
    await userEvent.click(screen.getByText('Yes, delete'))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('cancel button triggers onCancel', async () => {
    const onCancel = vi.fn()
    render(<ConfirmDialog open title="Delete?" onConfirm={vi.fn()} onCancel={onCancel} />)
    await userEvent.click(screen.getByText('Cancel'))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('clicking the backdrop triggers onCancel', () => {
    const onCancel = vi.fn()
    render(<ConfirmDialog open title="Delete?" onConfirm={vi.fn()} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('dialog'))
    expect(onCancel).toHaveBeenCalled()
  })

  it('clicking inside dialog box does not trigger onCancel', () => {
    const onCancel = vi.fn()
    render(<ConfirmDialog open title="Delete?" message="inside text" onConfirm={vi.fn()} onCancel={onCancel} />)
    fireEvent.click(screen.getByText('inside text'))
    expect(onCancel).not.toHaveBeenCalled()
  })
})

// ── PromptDialog ──────────────────────────────────────────────────────────────

describe('PromptDialog', () => {
  it('is not in the DOM when closed', () => {
    render(<PromptDialog open={false} title="Enter name" onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('pre-fills input with defaultValue', () => {
    render(<PromptDialog open title="Rename" defaultValue="Old name" onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect((screen.getByRole('textbox') as HTMLInputElement).value).toBe('Old name')
  })

  it('confirms with trimmed input value', async () => {
    const onConfirm = vi.fn()
    render(<PromptDialog open title="Rename" defaultValue="" onConfirm={onConfirm} onCancel={vi.fn()} />)
    await userEvent.type(screen.getByRole('textbox'), '  New Profile  ')
    await userEvent.click(screen.getByText('Save'))
    expect(onConfirm).toHaveBeenCalledWith('New Profile')
  })

  it('Enter key submits', async () => {
    const onConfirm = vi.fn()
    render(<PromptDialog open title="Rename" defaultValue="test" onConfirm={onConfirm} onCancel={vi.fn()} />)
    await userEvent.keyboard('{Enter}')
    expect(onConfirm).toHaveBeenCalledWith('test')
  })

  it('cancel button calls onCancel', async () => {
    const onCancel = vi.fn()
    render(<PromptDialog open title="Rename" onConfirm={vi.fn()} onCancel={onCancel} />)
    await userEvent.click(screen.getByText('Cancel'))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
