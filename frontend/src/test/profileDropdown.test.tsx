/**
 * ProfileDropdown integration tests.
 *
 * Exercises the click-outside / Escape close behaviour (the useClickOutside +
 * focus-trap hooks) through the real component, and profile switching — with
 * the network mocked at the boundary (MSW), not the client module.
 */

import { describe, it, expect } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { renderWithProviders } from './utils'
import { db } from './mocks/handlers'
import { ProfileDropdown } from '@/components/layout/ProfileDropdown'

function seedTwoProfiles() {
  db.profiles = [
    { slug: 'p1', name: 'p1', label: 'Primary', initials: 'P', color: '#3b82f6', active: true },
    { slug: 'p2', name: 'p2', label: 'Secondary', initials: 'S', color: '#f59e0b', active: false },
  ]
  db.activeSlug = 'p1'
}

describe('ProfileDropdown', () => {
  it('opens the menu when the avatar is clicked', async () => {
    seedTwoProfiles()
    renderWithProviders(<ProfileDropdown />)
    await waitFor(() => expect(screen.getByLabelText('Profile menu')).toBeInTheDocument())

    fireEvent.click(screen.getByLabelText('Profile menu'))
    await waitFor(() => expect(screen.getByRole('menu')).toBeInTheDocument())
    expect(screen.getByRole('menuitem', { name: /Secondary/i })).toBeInTheDocument()
  })

  it('closes when the user clicks outside', async () => {
    seedTwoProfiles()
    renderWithProviders(
      <div>
        <ProfileDropdown />
        <button>Elsewhere</button>
      </div>
    )
    await waitFor(() => expect(screen.getByLabelText('Profile menu')).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText('Profile menu'))
    await waitFor(() => expect(screen.getByRole('menu')).toBeInTheDocument())

    fireEvent.mouseDown(screen.getByText('Elsewhere'))
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
  })

  it('closes on Escape', async () => {
    seedTwoProfiles()
    renderWithProviders(<ProfileDropdown />)
    await waitFor(() => expect(screen.getByLabelText('Profile menu')).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText('Profile menu'))
    await waitFor(() => expect(screen.getByRole('menu')).toBeInTheDocument())

    fireEvent.keyDown(screen.getByRole('menu'), { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
  })

  it('switching profiles marks the newly-selected one active', async () => {
    seedTwoProfiles()
    renderWithProviders(<ProfileDropdown />)
    await waitFor(() => expect(screen.getByLabelText('Profile menu')).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText('Profile menu'))
    await waitFor(() => expect(screen.getByRole('menu')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('menuitem', { name: /Secondary/i }))

    await waitFor(() => expect(db.activeSlug).toBe('p2'))
  })
})
