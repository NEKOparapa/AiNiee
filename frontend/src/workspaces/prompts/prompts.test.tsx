import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import i18n from '@/i18n'
import { useConnectionStore } from '@/stores/connection'
import type { PromptDocument } from '@/api/prompts'
import { TextPromptPage } from './TextPromptPage'

let client: QueryClient
let stored: PromptDocument
let writes: PromptDocument[]
beforeEach(async () => {
  await i18n.changeLanguage('zh-CN')
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  useConnectionStore.getState().connect('http://127.0.0.1:8000', 'fixed-prompt-token')
  stored = { enabled: false, content: 'Initial world', rows: [], selected_id: null }
  writes = []
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    expect(request.headers.get('Authorization')).toBe('Bearer fixed-prompt-token')
    if (new URL(request.url).pathname === '/api/v1/config') return new Response('{}', { headers: { 'Content-Type': 'application/json' } })
    if (request.method === 'PUT') { stored = await request.json(); writes.push(stored) }
    return new Response(JSON.stringify(stored), { headers: { 'Content-Type': 'application/json' } })
  }))
})
afterEach(() => { client.clear(); vi.unstubAllGlobals() })

it('saves world content and enablement then shows the persisted response', async () => {
  render(<QueryClientProvider client={client}><TextPromptPage kind="world"/></QueryClientProvider>)
  await screen.findByDisplayValue('Initial world')
  fireEvent.change(screen.getByRole('textbox', { name: '提示内容' }), { target: { value: 'Updated world' } })
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]).toMatchObject({ content: 'Updated world', enabled: true })
  await screen.findByText('已保存')
  expect(screen.getByRole('textbox')).toHaveValue('Updated world')
})

it('preserves unedited example metadata through editing and save', async () => {
  stored = { enabled: true, rows: [{ src: 'hello', dst: '你好', provenance: { original: true } }] }
  render(<QueryClientProvider client={client}><TextPromptPage kind="examples"/></QueryClientProvider>)
  await screen.findByDisplayValue('你好')
  fireEvent.change(screen.getByRole('textbox', { name: '译文 1' }), { target: { value: '您好' } })
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(writes[0]?.rows?.[0]).toEqual({ src: 'hello', dst: '您好', provenance: { original: true } }))
})
