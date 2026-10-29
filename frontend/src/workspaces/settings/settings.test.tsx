import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createInstance } from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ApiConfig, ConfigPatch } from '@/api/types'
import { useConnectionStore } from '@/stores/connection'
import { AdvancedSettingsPage } from './AdvancedSettingsPage'
import { OutputSettingsPage } from './OutputSettingsPage'
import { TaskSettingsPage } from './TaskSettingsPage'
import { enSettings, zhSettings } from './translations'

function configFixture(overrides: Partial<ApiConfig> = {}): ApiConfig {
  return {
    lines_limit_switch: false, tokens_limit_switch: true, lines_limit: 10,
    tokens_limit: 1024, user_thread_counts: 0, request_timeout: 120, round_limit: 10,
    label_output_path: 'D:/custom/output', label_polish_output_path: 'D:/custom/polish',
    auto_set_output_path: true, output_filename_suffix: '_translated',
    bilingual_text_order: 'translation_first', translation_result_check_switch: false,
    response_conversion_toggle: false, opencc_preset: 's2t', keep_original_encoding: false,
    extract_task_token_limit: 10000, auto_extract_non_translate_switch: false,
    extract_short_name_merge_switch: true, source_language: 'auto', target_language: 'chinese_simplified',
    language_filter_switch: false, code_filter_switch: false, pre_line_counts: 0,
    few_shot_and_example_switch: true, auto_process_text_code_segment: false, text_symbol_repair_switch: false,
    response_check_switch: {
      return_to_original_text_check: true, residual_original_text_check: true,
      newline_character_count_check: true, reply_format_check: false,
    },
    polishing_pre_line_counts: 10, theme: 'auto', accent_color: '#808b9d', interface_language_setting: '简中',
    extension: { keep: true }, ...overrides,
  }
}

const clients: QueryClient[] = []

afterEach(() => {
  for (const client of clients) client.clear()
  clients.length = 0
  vi.unstubAllGlobals()
  useConnectionStore.getState().disconnect()
})

async function mountPage(page: ReactNode, options: {
  config?: Partial<ApiConfig>
  language?: 'zh' | 'en'
  failFirstPatch?: boolean
  connected?: boolean
} = {}) {
  let config = configFixture(options.config)
  const patches: ConfigPatch[] = []
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    if (request.method === 'PATCH') {
      const patch = await request.json() as ConfigPatch
      patches.push(patch)
      if (options.failFirstPatch && patches.length === 1) {
        return Response.json({ detail: 'Fixed mock failure' }, { status: 503 })
      }
      config = { ...config, ...patch } as ApiConfig
    }
    return Response.json(config)
  }))
  if (options.connected === false) useConnectionStore.getState().disconnect()
  else useConnectionStore.getState().connect('http://127.0.0.1:8999', 'fixed-test-token')
  const i18n = createInstance()
  await i18n.use(initReactI18next).init({
    lng: options.language ?? 'zh', fallbackLng: 'zh',
    resources: { zh: { settings: zhSettings }, en: { settings: enSettings } },
    interpolation: { escapeValue: false },
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } })
  clients.push(client)
  const result = render(<QueryClientProvider client={client}><I18nextProvider i18n={i18n}>{page}</I18nextProvider></QueryClientProvider>)
  return { ...result, user: userEvent.setup(), patches, serverConfig: () => config }
}

describe('settings workflows', () => {
  it('explains how to connect instead of showing a permanent loader while disconnected', async () => {
    await mountPage(<TaskSettingsPage />, { connected: false })
    expect(screen.getByRole('status')).toHaveTextContent('请先通过顶栏的连接按钮连接后端')
    expect(screen.queryByLabelText('正在加载设置…')).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: '任务切分模式' })).not.toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('switches both splitting flags atomically and saves a number only on commit', async () => {
    const { user, patches } = await mountPage(<TaskSettingsPage />)
    const mode = await screen.findByRole('combobox', { name: '任务切分模式' })
    await user.selectOptions(mode, 'lines')
    const lines = await screen.findByRole('spinbutton', { name: '任务的文本行数' })
    expect(patches[0]).toEqual({ lines_limit_switch: true, tokens_limit_switch: false })
    await user.clear(lines)
    await user.type(lines, '24')
    expect(patches).toHaveLength(1)
    await user.keyboard('{Enter}')
    await waitFor(() => expect(patches[1]).toEqual({ lines_limit: 24 }))
    await waitFor(() => expect(lines).toBeEnabled())
    await user.clear(lines)
    await user.type(lines, '-1{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('请输入 0 到 9999999 之间的整数')
    expect(patches).toHaveLength(2)
  })

  it('retains custom output paths while automatic folders are enabled', async () => {
    const { user, patches, serverConfig } = await mountPage(<OutputSettingsPage />)
    const path = await screen.findByRole('textbox', { name: '翻译输出文件夹' })
    expect(path).toBeDisabled()
    expect(path).toHaveValue('D:/custom/output')
    await user.click(screen.getByRole('switch', { name: '自动设置输出文件夹' }))
    await waitFor(() => expect(path).toBeEnabled())
    await user.clear(path)
    await user.type(path, 'D:/new/output{Enter}')
    await waitFor(() => expect(patches[1]).toEqual({ label_output_path: 'D:/new/output' }))
    expect(serverConfig().label_polish_output_path).toBe('D:/custom/polish')
    expect(serverConfig().extension).toEqual({ keep: true })
  })

  it('shows a failed save and retries the same draft without claiming success', async () => {
    const { user, patches } = await mountPage(<TaskSettingsPage />, { failFirstPatch: true })
    const timeout = await screen.findByRole('spinbutton', { name: '请求超时时间' })
    await user.clear(timeout)
    await user.type(timeout, '180{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('保存失败')
    expect(screen.queryByText('已保存')).not.toBeInTheDocument()
    expect(timeout).toHaveValue(180)
    await user.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByText('已保存')).toBeInTheDocument()
    expect(patches).toEqual([{ request_timeout: 180 }, { request_timeout: 180 }])
  })

  it('edits nested checks without dropping sibling values and exposes all advanced tabs', async () => {
    const { user, patches } = await mountPage(<AdvancedSettingsPage />)
    const check = await screen.findByRole('switch', { name: '回复格式强检查' })
    await user.click(check)
    await waitFor(() => expect(patches[0]).toEqual({ response_check_switch: {
      return_to_original_text_check: true, residual_original_text_check: true,
      newline_character_count_check: true, reply_format_check: true,
    } }))
    await user.click(screen.getByRole('tab', { name: '提取设置' }))
    expect(screen.getByRole('spinbutton', { name: '提取任务的 Token 切分数' })).toHaveValue(10000)
    await user.click(screen.getByRole('tab', { name: '润色设置' }))
    expect(screen.getByRole('spinbutton', { name: '润色参考上文行数' })).toHaveValue(10)
  })

  it('uses English labels and displays the legacy bilingual source-first value', async () => {
    await mountPage(<OutputSettingsPage />, { language: 'en', config: { bilingual_text_order: 'original_first' } })
    expect(await screen.findByRole('combobox', { name: 'Bilingual text order' })).toHaveValue('source_first')
    expect(screen.getByRole('heading', { name: 'Output settings' })).toBeInTheDocument()
  })
})
