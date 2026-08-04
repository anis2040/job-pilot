import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TagInput } from '@/components/ui/TagInput'

// ── TagInput ────────────────────────────────────────────────────────────────

describe('TagInput', () => {
  it('renders existing tags', () => {
    render(<TagInput value={['react', 'typescript']} onChange={() => {}} />)
    expect(screen.getByText('react')).toBeInTheDocument()
    expect(screen.getByText('typescript')).toBeInTheDocument()
  })

  it('adds a tag on Enter', async () => {
    const onChange = vi.fn()
    render(<TagInput value={[]} onChange={onChange} placeholder="Add tag" />)
    const input = screen.getByRole('textbox')
    await userEvent.type(input, 'python{Enter}')
    expect(onChange).toHaveBeenCalledWith(['python'])
  })

  it('adds a tag on comma', async () => {
    const onChange = vi.fn()
    render(<TagInput value={[]} onChange={onChange} />)
    const input = screen.getByRole('textbox')
    await userEvent.type(input, 'node,')
    expect(onChange).toHaveBeenCalledWith(['node'])
  })

  it('does not add duplicate tags', async () => {
    const onChange = vi.fn()
    render(<TagInput value={['react']} onChange={onChange} />)
    const input = screen.getByRole('textbox')
    await userEvent.type(input, 'react{Enter}')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('removes a tag when ✕ is clicked', async () => {
    const onChange = vi.fn()
    render(<TagInput value={['react', 'vue']} onChange={onChange} />)
    const removeBtn = screen.getByLabelText('Remove react')
    await userEvent.click(removeBtn)
    expect(onChange).toHaveBeenCalledWith(['vue'])
  })

  it('removes last tag on Backspace when input is empty', async () => {
    const onChange = vi.fn()
    render(<TagInput value={['react', 'vue']} onChange={onChange} />)
    const input = screen.getByRole('textbox')
    await userEvent.click(input)
    await userEvent.keyboard('{Backspace}')
    expect(onChange).toHaveBeenCalledWith(['react'])
  })

  it('normalises tag to lowercase', async () => {
    const onChange = vi.fn()
    render(<TagInput value={[]} onChange={onChange} />)
    const input = screen.getByRole('textbox')
    await userEvent.type(input, 'PYTHON{Enter}')
    expect(onChange).toHaveBeenCalledWith(['python'])
  })
})
