import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { components } from '@/api/generated/schema'
import type { Item } from '@/api/items'
import i18n from '@/i18n'
import { useConnectionStore } from '@/stores/connection'
import { useUiContextStore } from '@/stores/ui-context'
import { ItemsPage, VirtualItemTable } from './ItemsPage'

const item: Item = { id: '["nested/chapter.txt",10]', file: 'nested/chapter.txt', index: 10, position: 0, source_text: 'Fixed source', translated_text: '固定译文', translation_status: 1, flagged: false, model: 'mock' }
const current: components['schemas']['ProjectCurrentResponse'] = { project: { project_id: 'items-project', project_name: 'Test', project_type: 'Txt', project_create_time: '', input_path: '', file_count: 1, item_count: 1 }, supported_project_types: [], selected_project_type: 'Txt', configured_path: '' }
const clients: QueryClient[] = []
beforeEach(async () => {
  await i18n.changeLanguage('zh-CN')
  useConnectionStore.getState().connect('http://127.0.0.1:8000', 'fixed-token')
  useUiContextStore.getState().setSelectedItemIds([])
  window.history.replaceState({}, '', '/items')
})
afterEach(() => {
  for (const client of clients) client.clear()
  clients.length = 0
  vi.unstubAllGlobals(); vi.restoreAllMocks()
  useConnectionStore.getState().disconnect()
})
function mount(element: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  clients.push(client)
  return render(<QueryClientProvider client={client}><I18nextProvider i18n={i18n}><BrowserRouter>{element}</BrowserRouter></I18nextProvider></QueryClientProvider>)
}

describe('item proofreading', () => {
  it('virtualizes 50,000 rows and preserves a far-away highlighted row', () => {
    const rows: Item[] = Array.from({ length: 50000 }, (_, index) => ({ ...item, id: String(index), index, position: index, source_text: `Line ${index}` }))
    mount(<VirtualItemTable items={rows} selected={[]} highlighted={40000} onSelect={vi.fn()} onSelectAll={vi.fn()} onSave={vi.fn()} pending={false}/>)
    expect(screen.getAllByRole('row').length).toBeLessThan(20)
    expect(screen.getByText('Line 40000')).toBeVisible()
    expect(screen.getByRole('table')).toHaveAttribute('aria-rowcount', '50001')
    expect(screen.getByText('Line 40000').closest('[role="row"]')).toHaveClass('highlighted')
  })

  it('filters, selects multiple items and saves inline translation with generated API contracts', async () => {
    let translated = item.translated_text
    const queries: URL[] = []
    const edits: unknown[] = []
    vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
      const url = new URL(request.url)
      if (request.method === 'PATCH') { expect(decodeURIComponent(url.pathname)).toBe('/api/v1/projects/current/items/nested/chapter.txt/10'); const body = await request.json(); edits.push(body); translated = body.translated_text; return Response.json({ ...item, translated_text: translated }) }
      if (url.pathname.endsWith('/current')) return Response.json(current)
      if (url.pathname.endsWith('/files')) return Response.json([])
      if (url.pathname.endsWith('/items')) { queries.push(url); return Response.json({ project_id: 'items-project', items: [{ ...item, translated_text: translated }, { ...item, id: 'second', index: 20, position: 1 }], total: 2, page: 1, size: 100 }) }
      if (url.pathname.endsWith('/stats')) return Response.json({})
      throw new Error(`Unexpected request ${url}`)
    }))
    mount(<ItemsPage/>)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('checkbox', { name: '选择条目 1' }))
    expect(screen.getByText('#1')).toBeVisible()
    expect(screen.getByText('#2')).toBeVisible()
    expect(screen.queryByText('#11')).not.toBeInTheDocument()
    expect(screen.queryByText('#21')).not.toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: '选择当前页' }))
    expect(useUiContextStore.getState().selectedItemIds).toEqual([item.id, 'second'])
    await user.click(screen.getByRole('checkbox', { name: '选择当前页' }))
    expect(useUiContextStore.getState().selectedItemIds).toEqual([])
    await user.click(screen.getByRole('checkbox', { name: '选择条目 1' }))
    await user.click(screen.getByRole('checkbox', { name: '选择条目 2' }))
    expect(useUiContextStore.getState().selectedItemIds).toEqual([item.id, 'second'])
    await user.type(screen.getByRole('textbox', { name: '搜索原文与译文' }), 'Fixed')
    await user.click(screen.getByRole('button', { name: '筛选' }))
    await waitFor(() => expect(useUiContextStore.getState().filters.q).toBe('Fixed'))
    await waitFor(() => expect(queries.some(url => url.searchParams.get('q') === 'Fixed')).toBe(true))
    await user.click((await screen.findAllByRole('button', { name: '编辑译文' }))[0])
    const editor = screen.getByRole('textbox', { name: '编辑译文' })
    await user.clear(editor); await user.type(editor, '人工修改')
    await user.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(edits).toEqual([{ project_id: 'items-project', translated_text: '人工修改' }]))
    expect(await screen.findByText('条目已保存')).toBeVisible()
  })

  it('keeps the editor open and displays a safe error when saving fails', async () => {
    const onSave = vi.fn().mockRejectedValue(new Error('fixed failure'))
    mount(<VirtualItemTable items={[item]} selected={[]} highlighted={10} onSelect={vi.fn()} onSelectAll={vi.fn()} onSave={onSave} pending={false}/>)
    expect(screen.getByText('#1').closest('[role="row"]')).toHaveClass('highlighted')
    fireEvent.click(screen.getByRole('button', { name: '编辑译文' }))
    fireEvent.change(screen.getByRole('textbox', { name: '编辑译文' }), { target: { value: 'draft' } })
    fireEvent.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(item, 'translated_text', 'draft'))
    expect(screen.getByRole('textbox', { name: '编辑译文' })).toHaveValue('draft')
  })

  it('jumps directly to the last page and back without loading the full project into the DOM', async () => {
    const pages: number[] = []
    vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
      const url = new URL(request.url)
      if (url.pathname.endsWith('/current')) return Response.json(current)
      if (url.pathname.endsWith('/files')) return Response.json([])
      if (url.pathname.endsWith('/items')) {
        const page = Number(url.searchParams.get('page') ?? 1)
        pages.push(page)
        const start = (page - 1) * 100
        const response: components['schemas']['ItemListResponse'] = {
          project_id: 'items-project', total: 50000, page, size: 100,
          items: Array.from({ length: 100 }, (_, offset) => ({ ...item, id: String(start + offset), index: start + offset, position: start + offset, source_text: `Large source ${start + offset}` })),
        }
        return Response.json(response)
      }
      throw new Error(`Unexpected request ${url}`)
    }))
    mount(<ItemsPage/>)
    const user = userEvent.setup()
    expect(await screen.findByText('Large source 0')).toBeVisible()
    await user.click(screen.getByRole('button', { name: '最后一页' }))
    expect(await screen.findByText('Large source 49900')).toBeVisible()
    expect(screen.getAllByRole('row').length).toBeLessThan(20)
    expect(pages).toEqual([1, 500])
    await user.click(screen.getByRole('button', { name: '第一页' }))
    expect(await screen.findByText('Large source 0')).toBeVisible()
    expect(new URLSearchParams(window.location.search).get('page')).toBe('1')
  })
})
