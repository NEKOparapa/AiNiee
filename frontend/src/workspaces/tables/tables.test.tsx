import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import i18n from '@/i18n'
import { useConnectionStore } from '@/stores/connection'
import { tableKeys, type TableCollection, type TableImportRequest } from '@/api/tables'
import { TablesPage } from './TablesPage'

let client: QueryClient
let data: TableCollection
let saved: TableCollection[]
let uploads: TableImportRequest[]
let exported: string[]
beforeEach(async () => {
  await i18n.changeLanguage('zh-CN')
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  useConnectionStore.getState().connect('http://127.0.0.1:8000', 'fixed-table-token')
  data = { tables: [], active_table_id: null }; saved = []; uploads = []; exported = []
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', '') } })
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    expect(request.headers.get('Authorization')).toBe('Bearer fixed-table-token')
    const url = new URL(request.url)
    if (request.method === 'PUT') { data = await request.json(); saved.push(data) }
    if (url.pathname.endsWith('/export')) { exported.push(url.search); return new Response(JSON.stringify({ filename: 'tables.json', media_type: 'application/json', content_base64: btoa('[]') }), { headers: { 'Content-Type': 'application/json' } }) }
    if (url.pathname.endsWith('/import')) {
      const body: TableImportRequest = await request.json(); uploads.push(body)
      const imported = { id: 'import-0', name: 'Imported', enabled: true, rows: [{ src: 'Alice', dst: '爱丽丝' }] }
      if (body.preview) return new Response(JSON.stringify({ tables: [imported], active_table_id: imported.id }), { headers: { 'Content-Type': 'application/json' } })
      data = { tables: [...data.tables, imported], active_table_id: imported.id }
    }
    return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } })
  }))
})
afterEach(() => { client.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

function show() { render(<QueryClientProvider client={client}><TablesPage name="glossary"/></QueryClientProvider>) }

it('creates, edits and deletes a subtable, preserving row and table metadata', async () => {
  data = { tables: [{ id: 'one', name: 'Existing', enabled: true, rows: [{ src: 'Alpha', dst: '一', extra: { keep: true } }], future: 3 }], active_table_id: 'one' }
  show()
  await screen.findByDisplayValue('Existing')
  fireEvent.change(screen.getByRole('textbox', { name: '译文 1' }), { target: { value: 'Edited' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  await waitFor(() => expect(saved).toHaveLength(1))
  expect(saved[0].tables[0]).toMatchObject({ future: 3, rows: [{ src: 'Alpha', dst: 'Edited', extra: { keep: true } }] })
  await screen.findByText('已保存')
  fireEvent.click(screen.getByRole('button', { name: '新建子表' }))
  fireEvent.change(screen.getByRole('textbox', { name: '子表名称' }), { target: { value: 'Second' } })
  fireEvent.click(screen.getByRole('button', { name: '添加条目' }))
  fireEvent.change(screen.getByRole('textbox', { name: '原文 1' }), { target: { value: 'Beta' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  await waitFor(() => expect(saved).toHaveLength(2))
  await screen.findByText('已保存')
  expect(saved[1].tables).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: '删除子表' }))
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '删除子表' }))
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  await waitFor(() => expect(saved[2].tables).toHaveLength(1))
})

it('previews an uploaded file before confirming import and supports downloading a bundle', async () => {
  const user = userEvent.setup()
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:test') })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  show()
  await screen.findByText('尚无子表，请新建或导入。')
  fireEvent.click(screen.getByRole('button', { name: '导入' }))
  await user.upload(screen.getByLabelText('选择文件'), new File(['[{"src":"Alice","dst":"爱丽丝"}]'], 'terms.json', { type: 'application/json' }))
  await screen.findByText('Imported')
  expect(data.tables).toHaveLength(0)
  expect(uploads[0].preview).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '导入选中子表' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(uploads[1]).toMatchObject({ filename: 'terms.json', mode: 'new', selected_table_ids: ['import-0'] })
  fireEvent.click(screen.getByRole('button', { name: '导出所有子表' }))
  await waitFor(() => expect(exported).toHaveLength(1))
  expect(exported[0]).toContain('bundle=true')
  expect(URL.createObjectURL).toHaveBeenCalled()
})

it.each(['before', 'during'])('a GET begun %s a save cannot overwrite the newer PUT response', async race => {
  const stale: TableCollection = { tables: [{ id: 'one', name: 'Existing', enabled: true, rows: [{ src: 'Alpha', dst: 'Old' }] }], active_table_id: 'one' }
  let reads = 0
  let finishGet: (() => void) | undefined
  let finishPut: (() => void) | undefined
  const response = (body: TableCollection) => new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } })
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    if (request.method === 'PUT') {
      const body = await request.json()
      return new Promise<Response>(resolve => { finishPut = () => resolve(response(body)) })
    }
    if (++reads === 1) return response(stale)
    return new Promise<Response>(resolve => { finishGet = () => resolve(response(stale)) })
  }))
  show()
  await screen.findByDisplayValue('Old')
  const refetch = async () => { await act(async () => { void client.invalidateQueries({ queryKey: [...tableKeys.all(useConnectionStore.getState().revision), 'glossary'] }) }); await waitFor(() => expect(finishGet).toBeDefined()) }
  if (race === 'before') await refetch()
  fireEvent.change(screen.getByRole('textbox', { name: '译文 1' }), { target: { value: 'New' } })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  await waitFor(() => expect(finishPut).toBeDefined())
  if (race === 'during') await refetch()
  await act(async () => { finishPut!() })
  await screen.findByText('已保存')
  await act(async () => { finishGet!(); await Promise.resolve() })
  expect(screen.getByRole('textbox', { name: '译文 1' })).toHaveValue('New')
  expect(client.getQueryData<TableCollection>([...tableKeys.all(useConnectionStore.getState().revision), 'glossary'])?.tables[0].rows?.[0].dst).toBe('New')
})
