import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router-dom'
import i18n from '@/i18n'
import { Sidebar } from './Sidebar'
import { WorkflowNavigation } from './WorkflowNavigation'

function Location() { return <output aria-label="route">{useLocation().pathname}</output> }
function media(matches = false) {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches, addEventListener: vi.fn(), removeEventListener: vi.fn() })))
}
beforeEach(async () => { media(); await i18n.changeLanguage('zh-CN') })
afterEach(() => vi.unstubAllGlobals())

describe('Fluent navigation', () => {
  it('reveals a deep-linked prompt and keeps child pages keyboard accessible', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={['/prompts/style']}>
      <Sidebar collapsed={false} mobileOpen={false} onToggle={vi.fn()} onExpand={vi.fn()} onNavigate={vi.fn()}/><Location/>
    </MemoryRouter>)
    const branch = screen.getByRole('button', { name: '翻译提示词' })
    await waitFor(() => expect(branch).toHaveAttribute('aria-expanded', 'true'))
    expect(screen.getByRole('link', { name: '翻译风格' })).toHaveAttribute('aria-current', 'page')
    branch.focus()
    await user.keyboard('{Enter}')
    expect(screen.queryByRole('link', { name: '基础提示' })).not.toBeInTheDocument()
    await user.keyboard('{Enter}')
    await user.click(screen.getByRole('link', { name: '基础提示' }))
    expect(screen.getByLabelText('route')).toHaveTextContent('/prompts/system')
  })
  it('opens the rail before revealing a branch on a narrow screen', async () => {
    media(true)
    const expand = vi.fn()
    const user = userEvent.setup()
    render(<MemoryRouter><Sidebar collapsed={false} mobileOpen={false} onToggle={vi.fn()} onExpand={expand} onNavigate={vi.fn()}/></MemoryRouter>)
    expect(screen.getByRole('button', { name: '展开导航' })).toHaveAttribute('aria-expanded', 'false')
    await user.click(screen.getByRole('button', { name: '文本替换' }))
    expect(expand).toHaveBeenCalledOnce()
    expect(screen.getByRole('button', { name: '文本替换' })).toHaveAttribute('aria-expanded', 'true')
  })
  it('keeps project workflow routes and return-to-projects reachable', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={['/items']}><WorkflowNavigation/><Location/></MemoryRouter>)
    expect(screen.getByRole('link', { name: '条目校对' })).toHaveAttribute('aria-current', 'page')
    await user.click(screen.getByRole('link', { name: '质量检查' }))
    expect(screen.getByLabelText('route')).toHaveTextContent('/checks')
    await user.click(screen.getByRole('link', { name: '返回项目' }))
    expect(screen.getByLabelText('route')).toHaveTextContent('/')
  })
})
