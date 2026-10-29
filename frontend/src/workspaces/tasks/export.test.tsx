import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { components } from '@/api/generated/schema'
import i18n from '@/i18n'
import { useConnectionStore } from '@/stores/connection'
import { useBackendStore } from '@/stores/backend'
import { ExportPage } from './ExportPage'

const task: components['schemas']['TaskCurrentResponse'] = { status: 'idle', project_id: 'export-project', project_name: 'Export project', progress: {} }
let client: QueryClient
beforeEach(async () => {
  await i18n.changeLanguage('zh-CN')
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  useConnectionStore.getState().connect('http://127.0.0.1:8000', 'fixed-export-token')
  useBackendStore.getState().reset()
})
afterEach(() => { client.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); useConnectionStore.getState().disconnect() })
const show = () => render(<QueryClientProvider client={client}><ExportPage/></QueryClientProvider>)

it('shows the connection state instead of claiming no project while disconnected', () => {
  useConnectionStore.getState().disconnect()
  const fetcher = vi.fn()
  vi.stubGlobal('fetch', fetcher)
  show()
  expect(screen.getByRole('status')).toHaveTextContent('连接本地服务')
  expect(screen.queryByText('请先打开项目')).not.toBeInTheDocument()
  expect(fetcher).not.toHaveBeenCalled()
})

it('distinguishes loading, failure and empty project states and allows retry', async () => {
  let resolve: ((value: Response) => void) | undefined
  const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(done => { resolve = done })).mockResolvedValue(Response.json({ ...task, project_id: null, project_name: null }))
  vi.stubGlobal('fetch', fetcher)
  show()
  expect(screen.getByRole('status')).toHaveTextContent('正在加载')
  expect(screen.queryByText('请先打开项目')).not.toBeInTheDocument()
  await waitFor(() => expect(resolve).toBeDefined())
  await act(async () => resolve!(Response.json({ detail: 'failure' }, { status: 500 })))
  expect(await screen.findByRole('alert')).toHaveTextContent('加载失败')
  fireEvent.click(screen.getByRole('button', { name: '重试' }))
  expect(await screen.findByText('请先打开项目')).toBeVisible()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it('blocks duplicate exports, preserves a failed path and clears old project results', async () => {
  let complete: ((value: Response) => void) | undefined
  const posts: unknown[] = []
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    if (request.method === 'GET') return Response.json(task)
    posts.push(await request.json())
    if (posts.length === 1) return new Promise<Response>(resolve => { complete = resolve })
    return Response.json({ output_path: 'D:/fixed-output', files: ['story.txt'] })
  }))
  show()
  const input = await screen.findByRole('textbox', { name: '输出文件夹' })
  fireEvent.change(input, { target: { value: 'D:/fixed-output' } })
  fireEvent.click(screen.getByRole('button', { name: '导出译文' }))
  await waitFor(() => expect(complete).toBeDefined())
  expect(input).toBeDisabled()
  expect(screen.getByRole('button', { name: '正在导出…' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '正在导出…' }))
  expect(posts).toHaveLength(1)
  await act(async () => complete!(Response.json({ detail: 'export_failed' }, { status: 500 })))
  expect(await screen.findByRole('alert')).toHaveTextContent('导出失败')
  expect(input).toHaveValue('D:/fixed-output')
  fireEvent.click(screen.getByRole('button', { name: '导出译文' }))
  expect(await screen.findByRole('heading', { name: '导出完成' })).toBeVisible()
  act(() => useBackendStore.getState().setCurrentTask({ ...task, project_id: 'different-project' }))
  await waitFor(() => expect(screen.queryByRole('heading', { name: '导出完成' })).not.toBeInTheDocument())
})
