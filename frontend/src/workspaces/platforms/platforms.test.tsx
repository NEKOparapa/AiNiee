import { StrictMode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import i18n from '@/i18n'
import { useConnectionStore } from '@/stores/connection'
import type { Platform, PlatformBindings, PlatformList, PlatformUpdate } from '@/api/platforms'
import type { components } from '@/api/generated/schema'
import { PlatformsPage } from './PlatformsPage'

const preset: Platform = {
  id: 'custom', tag: 'custom', name: '自定义接口', group: 'custom', model: 'initial-model',
  api_url: '', api_key: '', api_format: 'OpenAI', auto_complete: true, region: '', access_key: '', secret_key: '',
  rpm_limit: 3500, temperature: 1, think_switch: false, think_depth: 'low', thinking_budget: -1, thinking_level: 'high',
  tls_switch: false, extra_body: {}, extra_headers: {}, model_datas: ['initial-model'],
  format_datas: ['OpenAI', 'Anthropic', 'Google'], region_datas: [],
  key_in_settings: ['api_url', 'api_key', 'api_format', 'model', 'auto_complete', 'rpm_limit', 'temperature', 'think_switch', 'think_depth'],
  metadata: { fields: ['api_url', 'api_key', 'api_format', 'model', 'auto_complete', 'rpm_limit', 'temperature', 'think_switch', 'think_depth', 'tls_switch', 'extra_body', 'extra_headers'], think_depth_options: ['low', 'medium', 'high'], thinking_level_options: [] },
}

const configured: Platform = { ...preset, id: 'custom_123', tag: 'custom_123', name: '本地测试接口', api_url: 'http://127.0.0.1:9001/v1', api_key: 'fixed-platform-secret' }
let data: PlatformList
let client: QueryClient
let writes: { method: string; path: string; body: unknown }[]
let modelRequests: number
let failUpdate: boolean
let testResults: components['schemas']['PlatformTestResponse']
const originalShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal')

function response(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
}

beforeEach(async () => {
  await i18n.changeLanguage('zh-CN')
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  useConnectionStore.getState().connect('http://127.0.0.1:8000', 'fixed-session-token')
  data = { platforms: [], presets: [preset], bindings: { active: null, extract: null, translate: null, polish: null, proofread: null } }
  writes = []
  modelRequests = 0
  failUpdate = false
  testResults = { platform_id: configured.id, success_count: 1, failure_count: 0, results: [{ key_index: 1, success: true, error_code: null }] }
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', '') } })
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    expect(request.headers.get('Authorization')).toBe('Bearer fixed-session-token')
    const path = new URL(request.url).pathname
    if (request.method === 'GET' && path === '/api/v1/platforms') return response(data)
    if (request.method === 'GET' && path.endsWith('/models')) { modelRequests++; return response({ platform_id: configured.id, models: ['first-model', 'second-model'] }) }
    if (request.method === 'POST' && path === `/api/v1/platforms/${configured.id}/test`) {
      writes.push({ method: request.method, path, body: null })
      return response(testResults)
    }
    if (request.method === 'POST' && path === '/api/v1/platforms') {
      const body = await request.json()
      writes.push({ method: request.method, path, body })
      const created = { ...preset, ...body, id: 'custom_created', tag: 'custom_created' }
      data = { ...data, platforms: [...data.platforms, created] }
      return response(created)
    }
    if (request.method === 'PUT' && path === '/api/v1/platforms/bindings') {
      const body: PlatformBindings = await request.json()
      writes.push({ method: request.method, path, body })
      data = { ...data, bindings: body }
      return response(body)
    }
    if (request.method === 'PUT' && path === `/api/v1/platforms/${configured.id}`) {
      const body: PlatformUpdate = await request.json()
      writes.push({ method: request.method, path, body })
      if (failUpdate) return response({ detail: 'invalid_platform' }, 422)
      const updated = { ...configured, ...body }
      data = { ...data, platforms: data.platforms.map(item => item.id === configured.id ? updated : item) }
      return response(updated)
    }
    if (request.method === 'DELETE' && path === `/api/v1/platforms/${configured.id}`) {
      writes.push({ method: request.method, path, body: null })
      data = { ...data, platforms: [], bindings: { active: null, extract: null, translate: null, polish: null, proofread: null } }
      return response({ deleted: true })
    }
    throw new Error(`Unexpected request: ${request.method} ${path}`)
  }))
})

afterEach(() => {
  client.clear()
  vi.unstubAllGlobals()
  if (originalShowModal) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', originalShowModal)
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal')
})

function show() {
  return render(<StrictMode><QueryClientProvider client={client}><PlatformsPage/></QueryClientProvider></StrictMode>)
}

it('creates a preset-based interface with explicit credentials and no discovery or test request', async () => {
  const user = userEvent.setup()
  show()
  await screen.findByText('还没有添加接口')
  await user.click(screen.getAllByRole('button', { name: '添加接口' })[0]!)
  const dialog = screen.getByRole('dialog', { name: '添加接口' })
  await user.clear(within(dialog).getByLabelText('接口名称'))
  await user.type(within(dialog).getByLabelText('接口名称'), 'My interface')
  await user.clear(within(dialog).getByLabelText('模型名称'))
  await user.type(within(dialog).getByLabelText('模型名称'), 'fixed-model')
  await user.type(within(dialog).getByLabelText('接口地址'), 'http://127.0.0.1:9001/v1')
  await user.type(within(dialog).getByLabelText('API Key'), 'test-only-key')
  await user.click(within(dialog).getByRole('button', { name: '保存' }))
  await screen.findByRole('article', { name: 'My interface' })
  expect(writes).toEqual([{ method: 'POST', path: '/api/v1/platforms', body: {
    preset_id: 'custom', name: 'My interface', model: 'fixed-model', api_url: 'http://127.0.0.1:9001/v1', api_key: 'test-only-key',
  } }])
  expect(screen.queryByText('test-only-key')).not.toBeInTheDocument()
  expect(modelRequests).toBe(0)
})

it('edits only changed request parameters and keeps the form open on a failed save', async () => {
  data.platforms = [configured]
  failUpdate = true
  const user = userEvent.setup()
  show()
  const card = await screen.findByRole('article', { name: configured.name })
  await user.click(within(card).getByRole('button', { name: '编辑接口' }))
  const dialog = screen.getByRole('dialog', { name: '编辑接口' })
  await user.click(within(dialog).getByRole('tab', { name: '请求参数' }))
  fireEvent.change(within(dialog).getByLabelText('温度'), { target: { value: '0.7' } })
  fireEvent.change(within(dialog).getByLabelText('自定义请求头'), { target: { value: '{"x-session":"fixed"}' } })
  await user.click(within(dialog).getByRole('button', { name: '保存' }))
  await within(dialog).findByRole('alert')
  expect(writes[0]?.body).toEqual({ temperature: 0.7, extra_headers: { 'x-session': 'fixed' } })
  expect(within(dialog).getByLabelText('温度')).toHaveValue(0.7)
  failUpdate = false
  await user.click(within(dialog).getByRole('button', { name: '保存' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(writes).toHaveLength(2)
})

it('rejects invalid header JSON locally without sending a request', async () => {
  data.platforms = [configured]
  const user = userEvent.setup()
  show()
  const card = await screen.findByRole('article', { name: configured.name })
  await user.click(within(card).getByRole('button', { name: '编辑接口' }))
  const dialog = screen.getByRole('dialog', { name: '编辑接口' })
  await user.click(within(dialog).getByRole('tab', { name: '请求参数' }))
  fireEvent.change(within(dialog).getByLabelText('自定义请求头'), { target: { value: '{"Authorization": false}' } })
  await user.click(within(dialog).getByRole('button', { name: '保存' }))
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('请求头的值必须为字符串')
  expect(writes).toHaveLength(0)
})

it('saves a role binding and supports following the active interface', async () => {
  data.platforms = [configured]
  const user = userEvent.setup()
  show()
  const bindings = await screen.findByRole('region', { name: '功能接口绑定' })
  await user.selectOptions(within(bindings).getByLabelText('激活接口'), configured.id)
  await user.selectOptions(within(bindings).getByLabelText('翻译接口'), configured.id)
  await user.click(within(bindings).getByRole('button', { name: '保存' }))
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]?.body).toEqual({ active: configured.id, extract: null, translate: configured.id, polish: null, proofread: null })
  const refreshed = screen.getByRole('region', { name: '功能接口绑定' })
  await user.selectOptions(within(refreshed).getByLabelText('翻译接口'), '')
  await user.click(within(refreshed).getByRole('button', { name: '保存' }))
  await waitFor(() => expect(writes).toHaveLength(2))
  expect(writes[1]?.body).toEqual({ active: configured.id, extract: null, translate: null, polish: null, proofread: null })
})

it('fetches models once on demand, filters them, and makes a single selection current', async () => {
  data.platforms = [configured]
  const user = userEvent.setup()
  show()
  const card = await screen.findByRole('article', { name: configured.name })
  expect(modelRequests).toBe(0)
  await user.click(within(card).getByRole('button', { name: '浏览模型' }))
  const dialog = screen.getByRole('dialog')
  await within(dialog).findByLabelText('second-model')
  await user.type(within(dialog).getByRole('textbox', { name: '搜索模型' }), 'second')
  expect(within(dialog).queryByLabelText('first-model')).not.toBeInTheDocument()
  await user.click(within(dialog).getByLabelText('second-model'))
  await user.click(within(dialog).getByRole('button', { name: '添加所选模型' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(modelRequests).toBe(1)
  expect(writes[0]?.body).toEqual({ model_datas: ['initial-model', 'second-model'], model: 'second-model' })
})

it('confirms deletion before removing the interface', async () => {
  data.platforms = [configured]
  const user = userEvent.setup()
  show()
  const card = await screen.findByRole('article', { name: configured.name })
  await user.click(within(card).getByRole('button', { name: `删除接口 ${configured.name}` }))
  expect(writes).toHaveLength(0)
  const dialog = screen.getByRole('dialog', { name: '删除这个接口？' })
  await user.click(within(dialog).getByRole('button', { name: '删除接口' }))
  await screen.findByText('还没有添加接口')
  expect(writes).toEqual([{ method: 'DELETE', path: `/api/v1/platforms/${configured.id}`, body: null }])
})

it('tests the saved interface explicitly and shows success without displaying credentials', async () => {
  data.platforms = [configured]
  const user = userEvent.setup()
  show()
  const card = await screen.findByRole('article', { name: configured.name })
  expect(writes).toHaveLength(0)
  await user.click(within(card).getByRole('button', { name: '测试连接' }))
  const dialog = screen.getByRole('dialog', { name: `接口测试结果 · ${configured.name}` })
  await waitFor(() => expect(within(dialog).getByRole('status')).toHaveTextContent('成功 1，失败 0'))
  expect(within(dialog).getByText('连接成功')).toBeVisible()
  expect(dialog).not.toHaveTextContent(configured.api_key)
  expect(writes).toEqual([{ method: 'POST', path: `/api/v1/platforms/${configured.id}/test`, body: null }])
})

it('shows individual key outcomes and an accurate partial failure summary', async () => {
  data.platforms = [{ ...configured, api_key: 'first-secret,second-secret' }]
  testResults = { platform_id: configured.id, success_count: 1, failure_count: 1, results: [
    { key_index: 1, success: true, error_code: null }, { key_index: 2, success: false, error_code: 'platform_test_failed' },
  ] }
  const user = userEvent.setup()
  show()
  const card = await screen.findByRole('article', { name: configured.name })
  await user.click(within(card).getByRole('button', { name: '测试连接' }))
  const dialog = screen.getByRole('dialog', { name: `接口测试结果 · ${configured.name}` })
  await waitFor(() => expect(within(dialog).getByRole('status')).toHaveTextContent('成功 1，失败 1'))
  const results = within(dialog).getAllByRole('listitem')
  expect(results[0]).toHaveTextContent('Key 1连接成功')
  expect(results[1]).toHaveTextContent('Key 2连接失败')
  expect(dialog).not.toHaveTextContent('first-secret')
  expect(dialog).not.toHaveTextContent('second-secret')
})
