import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { components } from '@/api/generated/schema'
import type { AnalysisDocument } from '@/api/analysis'
import i18n from '@/i18n'
import { useConnectionStore } from '@/stores/connection'
import { useBackendStore } from '@/stores/backend'
import { useUiContextStore } from '@/stores/ui-context'
import { AnalysisPage } from './AnalysisPage'

const initial: AnalysisDocument = { project_id: 'analysis-ui', characters: [
  { source: 'Alice', recommended_translation: '爱丽丝', gender: '女', note: 'hero', occurrence_count: 4, extension: { keep: true } },
  { source: 'Bob', recommended_translation: '鲍勃', gender: '男', note: '', occurrence_count: 2 },
], terms: [], non_translate: [], metadata: { future: ['retained'] } }
const current: components['schemas']['ProjectCurrentResponse'] = { project: { project_id: 'analysis-ui', project_name: 'Test', project_type: 'Txt', project_create_time: '', input_path: '', file_count: 1, item_count: 1 }, supported_project_types: [], selected_project_type: 'Txt', configured_path: '' }
const clients: QueryClient[] = []
beforeEach(async () => { await i18n.changeLanguage('zh-CN'); useConnectionStore.getState().connect('http://127.0.0.1:8000', 'analysis-fixed-token'); useBackendStore.setState({ currentTask: null }); window.history.replaceState({}, '', '/analysis') })
afterEach(() => { clients.forEach(client => client.clear()); clients.length = 0; vi.unstubAllGlobals(); vi.restoreAllMocks(); useConnectionStore.getState().disconnect() })
function mount(fetcher: (request: Request) => Promise<Response>, mockTables = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  clients.push(client)
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    const path = new URL(request.url).pathname
    if (path.endsWith('/projects/current')) return Response.json(current)
    if (mockTables && path.includes('/tables/')) return Response.json({ tables: [], active_table_id: null })
    return fetcher(request)
  }))
  render(<QueryClientProvider client={client}><I18nextProvider i18n={i18n}><BrowserRouter><AnalysisPage/></BrowserRouter></I18nextProvider></QueryClientProvider>)
}

it('filters and edits analysis while retaining metadata and recording selected rows', async () => {
  let saved = structuredClone(initial)
  const writes: AnalysisDocument[] = []
  mount(async request => { if (request.method === 'PUT') { saved = await request.json(); writes.push(saved) }; return Response.json(saved) })
  const user = userEvent.setup()
  const translation = await screen.findByRole('textbox', { name: '建议译文 1' })
  await user.clear(translation); await user.type(translation, '艾丽斯')
  expect(screen.getByRole('button', { name: '导入 JSON' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: '保存修改' }))
  expect(await screen.findByText('修改已保存')).toBeVisible()
  expect(writes[0].metadata).toEqual(initial.metadata)
  expect(writes[0].characters[0].extension).toEqual({ keep: true })
  await user.selectOptions(screen.getByRole('combobox', { name: '筛选分类' }), '女')
  expect(screen.queryByRole('textbox', { name: '原文 2' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('checkbox', { name: /^1$/ }))
  expect(useUiContextStore.getState().selectedItemIds).toEqual(['analysis:analysis-ui:characters:0'])
  expect(useUiContextStore.getState().filters).toEqual({ view: 'characters', q: '', category: '女' })
})

it('moves selected characters only after confirmation and publishes the selected identity', async () => {
  const requests: Array<{ path: string; body: unknown }> = []
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
  let snapshot = structuredClone(initial)
  mount(async request => {
    const path = new URL(request.url).pathname
    if (request.method === 'POST') {
      const body = await request.json(); requests.push({ path, body })
      if (path.endsWith('/move')) { snapshot = { ...snapshot, characters: [snapshot.characters[1]], terms: [{ source: 'Alice', recommended_translation: '爱丽丝', category_path: 'Identity', occurrence_count: 4, note: 'hero；原分类: 女' }] }; return Response.json(snapshot) }
      return Response.json({ added: 1, collection: { tables: [], active_table_id: null } })
    }
    return Response.json(snapshot)
  })
  const user = userEvent.setup()
  await user.click(await screen.findByRole('checkbox', { name: /^1$/ }))
  await user.type(screen.getByRole('textbox', { name: '目标分类' }), 'Identity')
  await user.click(screen.getByRole('button', { name: '移至术语' }))
  await waitFor(() => expect(requests[0]?.body).toEqual({ project_id: 'analysis-ui', identities: ['Alice'], target: 'terms', category: 'Identity' }))
  expect(confirm).toHaveBeenCalledWith(expect.stringContaining('相同原文会被覆盖'))
  await user.click(screen.getByRole('tab', { name: /^术语/ }))
  expect(await screen.findByRole('textbox', { name: '原文 1' })).toHaveValue('Alice')
  await user.click(screen.getByRole('button', { name: '写入公共表格' }))
  expect(await screen.findByText('已追加 1 条，已有原文保持不变。')).toBeVisible()
  expect(requests[1]?.body).toEqual({ project_id: 'analysis-ui', table_id: null, identities: ['Alice'] })
})

it('keeps edits after a failed save and requires confirmation before deleting', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  mount(async request => request.method === 'PUT' ? Response.json({ detail: 'project_changed' }, { status: 409 }) : Response.json(initial))
  const user = userEvent.setup()
  const field = await screen.findByRole('textbox', { name: '备注 1' })
  fireEvent.change(field, { target: { value: 'unsaved' } })
  await user.click(screen.getByRole('button', { name: '保存修改' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('当前项目已切换')
  expect(field).toHaveValue('unsaved')
  await user.click(screen.getByRole('checkbox', { name: /^1$/ }))
  await user.click(screen.getByRole('button', { name: '删除所选' }))
  expect(screen.getByRole('textbox', { name: '原文 1' })).toHaveValue('Alice')
  await user.click(screen.getByRole('button', { name: '重新加载' }))
  expect(confirm).toHaveBeenLastCalledWith(expect.stringContaining('放弃未保存'))
  expect(field).toHaveValue('unsaved')
  confirm.mockReturnValue(true)
  await user.click(screen.getByRole('button', { name: '重新加载' }))
  await waitFor(() => expect(field).toHaveValue('hero'))
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it('offers a retry after an analysis read fails without presenting an editable empty result', async () => {
  let reads = 0
  mount(async () => ++reads === 1 ? Response.json({ detail: 'failure' }, { status: 500 }) : Response.json(initial))
  expect(await screen.findByRole('alert')).toHaveTextContent('加载失败')
  expect(screen.queryByRole('button', { name: '添加条目' })).not.toBeInTheDocument()
  expect(screen.queryByText('请先打开项目')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '重试' }))
  expect(await screen.findByRole('textbox', { name: '原文 1' })).toHaveValue('Alice')
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it('requires the public table list to load before publishing and lets users retry it', async () => {
  let reads = 0
  mount(async request => new URL(request.url).pathname.includes('/tables/')
    ? ++reads === 1 ? Response.json({ detail: 'failure' }, { status: 500 }) : Response.json({ tables: [], active_table_id: null })
    : Response.json(initial), false)
  await screen.findByRole('textbox', { name: '原文 1' })
  expect(await screen.findByRole('alert')).toHaveTextContent('加载失败')
  expect(screen.getByRole('button', { name: '写入公共表格' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '重试' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '写入公共表格' })).toBeEnabled())
})

it('keeps the active draft and view fixed until a pending save returns', async () => {
  let complete: ((response: Response) => void) | undefined
  const writes: AnalysisDocument[] = []
  mount(async request => {
    if (request.method !== 'PUT') return Response.json(initial)
    writes.push(await request.json())
    return new Promise<Response>(resolve => { complete = resolve })
  })
  const field = await screen.findByRole('textbox', { name: '备注 1' })
  fireEvent.change(field, { target: { value: 'pending draft' } })
  fireEvent.click(screen.getByRole('button', { name: '保存修改' }))
  await waitFor(() => expect(complete).toBeDefined())
  expect(field).toBeDisabled()
  expect(screen.getByRole('button', { name: '放弃修改' })).toBeDisabled()
  expect(screen.getByRole('tab', { name: /^术语/ })).toBeDisabled()
  fireEvent.click(screen.getByRole('tab', { name: /^术语/ }))
  expect(screen.getByRole('textbox', { name: '备注 1' })).toHaveValue('pending draft')
  await act(async () => complete!(Response.json(writes[0])))
  expect(await screen.findByText('修改已保存')).toBeVisible()
  expect(field).toBeEnabled()
  expect(field).toHaveValue('pending draft')
})
