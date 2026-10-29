import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import i18n from '@/i18n'
import type { PromptLibrary } from '@/api/prompts'
import { useConnectionStore } from '@/stores/connection'
import { PromptLibraryPage } from './PromptLibraryPage'

let client: QueryClient
let data: PromptLibrary
let writes: unknown[]
beforeEach(async () => {
  await i18n.changeLanguage('zh-CN')
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  useConnectionStore.getState().connect('http://127.0.0.1:8000', 'fixed-library-token')
  data = { presets: [{ id: 100, type: 'system', name: '通用', content: 'General preset' }], custom: [{ id: 'custom-1', type: 'user', name: '我的提示', content: 'Custom prose', future: 'retain' }], selected_id: 100 }
  writes = []
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', '') } })
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    expect(request.headers.get('Authorization')).toBe('Bearer fixed-library-token')
    if (request.method === 'POST') {
      const body = await request.json(); writes.push(body)
      const prompt = { ...body, id: body.id ?? 'created-id', type: 'user' as const }
      data.custom = [...data.custom.filter(item => item.id !== prompt.id), prompt]
      data.selected_id = prompt.id
    } else if (request.method === 'DELETE') {
      const id = new URL(request.url).searchParams.get('id')
      data.custom = data.custom.filter(item => item.id !== id)
      data.selected_id = 100
    } else if (request.method === 'PUT') {
      const body = await request.json(); writes.push(body); data.selected_id = body.selected_id
      return new Response(JSON.stringify({ selected_id: body.selected_id, content: 'Custom prose', enabled: true, rows: [] }), { headers: { 'Content-Type': 'application/json' } })
    }
    return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } })
  }))
})
afterEach(() => { client.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('lets users preview, search and explicitly select a custom prompt', async () => {
  render(<QueryClientProvider client={client}><PromptLibraryPage kind="system"/></QueryClientProvider>)
  await screen.findByText('General preset')
  fireEvent.change(screen.getByRole('textbox', { name: '搜索名称或内容' }), { target: { value: 'Custom prose' } })
  fireEvent.click(screen.getByRole('button', { name: '我的提示' }))
  expect(writes).toHaveLength(0)
  fireEvent.click(screen.getByRole('button', { name: '使用此提示' }))
  await waitFor(() => expect(writes).toEqual([{ selected_id: 'custom-1' }]))
  await waitFor(() => expect(screen.getByRole('button', { name: '当前使用' })).toBeDisabled())
})

it('localizes system preset names when switching language', async () => {
  await i18n.changeLanguage('en')
  render(<QueryClientProvider client={client}><PromptLibraryPage kind="system"/></QueryClientProvider>)
  await screen.findByRole('button', { name: 'General' })
  expect(screen.getByText('System presets are read only. Make a custom copy to edit them.')).toBeInTheDocument()
})

it('creates and edits a custom prompt while retaining its extra fields', async () => {
  render(<QueryClientProvider client={client}><PromptLibraryPage kind="system"/></QueryClientProvider>)
  await screen.findByText('General preset')
  fireEvent.click(screen.getByRole('button', { name: '新建提示词' }))
  let dialog = screen.getByRole('dialog')
  fireEvent.change(within(dialog).getByLabelText('名称'), { target: { value: 'New custom' } })
  fireEvent.change(within(dialog).getByLabelText('提示内容'), { target: { value: 'Created content' } })
  fireEvent.click(within(dialog).getByRole('button', { name: '保存' }))
  await screen.findByText('Created content')
  expect(data.selected_id).toBe('created-id')
  fireEvent.click(screen.getByRole('button', { name: '我的提示' }))
  fireEvent.click(screen.getByRole('button', { name: '编辑提示词' }))
  dialog = screen.getByRole('dialog')
  fireEvent.change(within(dialog).getByLabelText('提示内容'), { target: { value: 'Edited custom prose' } })
  fireEvent.click(within(dialog).getByRole('button', { name: '保存' }))
  await screen.findByText('Edited custom prose')
  expect(writes[1]).toMatchObject({ id: 'custom-1', future: 'retain' })
})

it('confirms deletion and falls back to the default preset', async () => {
  data.selected_id = 'custom-1'
  render(<QueryClientProvider client={client}><PromptLibraryPage kind="system"/></QueryClientProvider>)
  await screen.findByText('Custom prose')
  fireEvent.click(screen.getByRole('button', { name: '删除提示词' }))
  expect(data.custom).toHaveLength(1)
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '删除提示词' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(data.custom).toHaveLength(0)
  expect(screen.getByText('General preset')).toBeInTheDocument()
})
