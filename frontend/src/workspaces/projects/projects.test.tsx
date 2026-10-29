import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { I18nextProvider } from 'react-i18next'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/i18n'
import type { components } from '@/api/generated/schema'
import { useConnectionStore } from '@/stores/connection'
import { useUiContextStore } from '@/stores/ui-context'
import { droppedPath } from '../HomePage'
import { OverviewPage } from './OverviewPage'
import { ProjectHistory } from './ProjectHistory'

const current: components['schemas']['ProjectCurrentResponse'] = {
  project: { project_id: 'project-a', project_name: 'Fixed project', project_type: 'Txt', project_create_time: '2026-01-01T12:00:00', input_path: 'D:/source', file_count: 2, item_count: 5 },
  supported_project_types: ['AutoType', 'Txt'], selected_project_type: 'Txt', configured_path: 'D:/source',
}
const files: components['schemas']['ProjectFile'][] = [
  { path: 'chapters/one.txt', project_type: 'Txt', encoding: 'utf-8', item_count: 3, translated_count: 1, polished_count: 0, excluded_count: 0, questionable_count: 0, language_stats: [{ language: 'en', count: 3, confidence: 1 }] },
  { path: 'two.txt', project_type: 'Txt', encoding: 'utf-8', item_count: 2, translated_count: 0, polished_count: 0, excluded_count: 0, questionable_count: 0, language_stats: [] },
]
const stats: components['schemas']['ProjectStats'] = {
  total: 5, untranslated: 4, translated: 1, polished: 0, excluded: 0, questionable: 0, other: 0, progress: { token: 24 },
}
const historyEntries: components['schemas']['ProjectHistoryEntry'][] = [
  { project_id: 'project-a', project_name: 'Current project', project_create_time: '2026-01-02T12:00:00', total_line: 5, line: 1, is_complete: false, cache_path: 'D:/cache/project-a/AinieeCacheData.json' },
  { project_id: 'project-b', project_name: 'Previous project', project_create_time: '2026-01-01T12:00:00', total_line: 2, line: 2, is_complete: true, cache_path: 'D:/cache/project-b/AinieeCacheData.json' },
]
const clients: QueryClient[] = []
beforeEach(async () => {
  await i18n.changeLanguage('zh-CN')
  useConnectionStore.getState().connect('http://127.0.0.1:8000', 'fixed-test-token')
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', '') } })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open') } })
})
afterEach(() => {
  clients.forEach(client => client.clear()); clients.length = 0
  vi.unstubAllGlobals(); vi.restoreAllMocks()
  useConnectionStore.getState().disconnect()
  useUiContextStore.getState().setFilters({})
})
function mount(element: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  clients.push(client)
  return render(<QueryClientProvider client={client}><I18nextProvider i18n={i18n}><BrowserRouter>{element}</BrowserRouter></I18nextProvider></QueryClientProvider>)
}

describe('project workspaces', () => {
  it('uses complete dropped paths and never guesses a path from a folder name', () => {
    const data = (text = '', uri = '') => ({ getData: (type: string) => type === 'text/plain' ? text : type === 'text/uri-list' ? uri : '' }) as DataTransfer
    expect(droppedPath(data('D:\\books\\story'))).toBe('D:\\books\\story')
    expect(droppedPath(data('', 'file:///D:/books/story%20one'))).toBe('D:/books/story one')
    expect(droppedPath(data('story'))).toBeNull()
    expect(droppedPath(data('', 'https://example.invalid/story'))).toBeNull()
    expect(droppedPath(data())).toBeNull()
  })

  it('renders backend statistics and keeps file selection and filters in UI context', async () => {
    vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
      const path = new URL(request.url).pathname
      if (path.endsWith('/current')) return Response.json(current)
      if (path.endsWith('/files')) return Response.json(files)
      if (path.endsWith('/stats')) return Response.json(stats)
      throw new Error(`Unexpected request ${path}`)
    }))
    mount(<OverviewPage/>)
    const user = userEvent.setup()
    const first = await screen.findByRole('button', { name: /one.txt/ })
    await user.click(first)
    expect(useUiContextStore.getState().filters.file).toBe('chapters/one.txt')
    expect(screen.getByText('utf-8')).toBeVisible()
    expect(screen.getByRole('progressbar', { name: '已完成进度' })).toHaveAttribute('value', '1')
    await user.type(screen.getByRole('textbox', { name: '筛选文件' }), 'missing')
    expect(screen.getByText('没有匹配的文件')).toBeVisible()
    expect(useUiContextStore.getState().filters.q).toBe('missing')
    expect(screen.queryByRole('button', { name: /one.txt/ })).not.toBeInTheDocument()
  })

  it('requires confirmation to delete an inactive cache and disables current cache deletion', async () => {
    let entries = [...historyEntries]
    const requests: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
      if (request.method === 'DELETE') {
        requests.push(request.url)
        entries = entries.filter(entry => entry.project_id !== 'project-b')
        return Response.json({ deleted: true })
      }
      return Response.json(entries)
    }))
    const resume = vi.fn()
    mount(<ProjectHistory currentId="project-a" pending={false} onContinue={resume}/>)
    const user = userEvent.setup()
    await screen.findByRole('article', { name: 'Previous project' })
    expect(screen.getByRole('button', { name: '删除缓存 Current project' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: '继续项目' }))
    expect(resume).toHaveBeenCalledWith(historyEntries[1].cache_path)
    await user.click(screen.getByRole('button', { name: '删除缓存 Previous project' }))
    expect(requests).toHaveLength(0)
    const dialog = screen.getByRole('dialog', { name: '删除项目缓存？' })
    expect(within(dialog).getByText(/无法撤销/)).toBeVisible()
    await user.click(within(dialog).getByRole('button', { name: '取消' }))
    expect(requests).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: '删除缓存 Previous project' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '删除缓存' }))
    await waitFor(() => expect(screen.queryByRole('article', { name: 'Previous project' })).not.toBeInTheDocument())
    expect(requests).toEqual(['http://127.0.0.1:8000/api/v1/projects/history/project-b'])
  })

  it('shows a retry action when the current project cannot be read', async () => {
    let failed = true
    vi.stubGlobal('fetch', vi.fn(async () => failed ? Response.json({ detail: 'project_path_unreadable' }, { status: 403 }) : Response.json({ ...current, project: null })))
    mount(<OverviewPage/>)
    expect(await screen.findByRole('alert')).toHaveTextContent('无法读取此路径')
    failed = false
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByText('尚未打开项目')).toBeVisible()
  })
})
