import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { components } from '@/api/generated/schema'
import i18n from '@/i18n'
import { useConnectionStore } from '@/stores/connection'
import { useUiContextStore } from '@/stores/ui-context'
import { ChecksPage, issueLocation } from './ChecksPage'

const issue: components['schemas']['CheckIssue'] = { id: '["nested/章节.txt",401]', file: 'nested/章节.txt', index: 401, position: 201, error: '固定检查问题', source: 'Fixed source', translation: '固定译文' }
const current: components['schemas']['ProjectCurrentResponse'] = { project: { project_id: 'check-project', project_name: 'Test', project_type: 'Txt', project_create_time: '', input_path: '', file_count: 1, item_count: 1 }, supported_project_types: [], selected_project_type: 'Txt', configured_path: '' }
const config: Partial<components['schemas']['ConfigDocument']> = {
  rule_check_exclusion: true, rule_check_auto_process: true, rule_check_placeholder: true, rule_check_number: true, rule_check_example: true, rule_check_newline: true, rule_check_untranslated: true,
  check_lang_mode_text: 'judge', check_chunk_size: 20, check_threshold_ratio: 0.75, check_exclude_non_translate: true, prompt_dictionary_match_case_sensitive: false, prompt_dictionary_match_whole_word: false,
}
const clients: QueryClient[] = []
beforeEach(async () => { await i18n.changeLanguage('zh-CN'); useConnectionStore.getState().connect('http://127.0.0.1:8000', 'fixed-token'); window.history.replaceState({}, '', '/checks') })
afterEach(() => { clients.forEach(client => client.clear()); clients.length = 0; vi.unstubAllGlobals(); vi.restoreAllMocks(); useConnectionStore.getState().disconnect() })
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  clients.push(client)
  render(<QueryClientProvider client={client}><I18nextProvider i18n={i18n}><BrowserRouter><ChecksPage/></BrowserRouter></I18nextProvider></QueryClientProvider>)
}

it('links a check result to the correct stable index, file and pagination page', () => {
  const url = new URL(issueLocation(issue), 'http://localhost')
  expect(url.searchParams.get('file')).toBe(issue.file)
  expect(url.searchParams.get('index')).toBe('401')
  expect(url.searchParams.get('page')).toBe('3')
})

it('uses saved options and selects the clicked issue in UI context', async () => {
  const requests: unknown[] = []
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    const path = new URL(request.url).pathname
    if (path.endsWith('/current')) return Response.json(current)
    if (path.endsWith('/config')) return Response.json(config)
    if (path.endsWith('/checks/rule')) { requests.push(await request.json()); return Response.json({ kind: 'rule', project_id: 'check-project', passed: false, issues: [issue], reports: [], mode: null, target_language: null } satisfies components['schemas']['CheckResponse']) }
    throw new Error(`Unexpected request ${path}`)
  }))
  mount()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '开始检查' }))
  const link = await screen.findByRole('link', { name: '校对此条' })
  expect(screen.getByText(`${issue.file} · #202`)).toBeVisible()
  expect(screen.queryByText(`${issue.file} · #402`)).not.toBeInTheDocument()
  expect(requests).toEqual([{ rules: { exclusion: true, auto_process: true, placeholder: true, number: true, example: true, newline: true, untranslated: true } }])
  expect(link).toHaveAttribute('href', issueLocation(issue))
  await user.click(link)
  expect(useUiContextStore.getState().selectedItemIds).toEqual([issue.id])
})

it('renders application failures without raw server details', async () => {
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    const path = new URL(request.url).pathname
    if (path.endsWith('/current')) return Response.json(current)
    if (path.endsWith('/config')) return Response.json(config)
    return Response.json({ detail: 'operation_busy' }, { status: 409 })
  }))
  mount()
  await userEvent.setup().click(await screen.findByRole('button', { name: '开始检查' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('请等待当前任务结束后再检查。')
})
