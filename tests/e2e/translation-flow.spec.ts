import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { EOL } from 'node:os'
import { test, expect } from '../../frontend/playwright-fixtures'

test.use({ mockProviders: true })

test('translate, stop and continue, check a problem, edit and export the real project', async ({ page, backend }, testInfo) => {
  const source = join(backend.directory, 'input')
  const output = join(backend.directory, 'output')
  await mkdir(source)
  await writeFile(join(source, 'story.txt'), 'Hello, world!\nThis is a headless translation test.\nThe story continues here.\n', 'utf8')
  await writeFile(join(backend.directory, 'data', 'config.json'), JSON.stringify({
    source_language: 'english', target_language: 'chinese_simplified', translation_project: 'Txt',
    auto_set_output_path: false, label_output_path: output, label_polish_output_path: join(output, 'polish'),
    lines_limit_switch: true, tokens_limit_switch: false, lines_limit: 1, user_thread_counts: 1,
    round_limit: 1, pre_line_counts: 0, language_filter_switch: false, code_filter_switch: false,
    translation_result_check_switch: false, response_conversion_toggle: false,
    prompt_dictionary_switch: true, prompt_dictionary_data: [{ src: 'world', dst: '世界', info: '', regex: false }],
    platforms: { custom_platform_mock: { tag: 'custom_platform_mock', name: 'Fixed mock', api_url: 'https://llm.invalid/v1', api_format: 'OpenAI', api_key: 'e2e-private-key', model: 'fixed-mock-model', rpm_limit: 4096 } },
    api_settings: { active: 'custom_platform_mock', translate: 'custom_platform_mock', polish: 'custom_platform_mock' },
  }), 'utf8')
  await page.goto(backend.handoff('/'))
  await page.getByRole('textbox', { name: '项目路径', exact: true }).fill(source)
  await page.getByRole('combobox', { name: '项目类型', exact: true }).selectOption('Txt')
  await page.getByRole('button', { name: '打开项目', exact: true }).click()
  await expect(page.getByRole('heading', { name: '项目概览', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '开始翻译', exact: true }).click()
  await expect(page.locator('.task-progress')).toContainText('1 / 3')
  await page.getByRole('button', { name: '停止任务', exact: true }).click()
  await expect(page.locator('.task-status')).toHaveText('已停止', { timeout: 15000 })
  await page.getByRole('button', { name: '继续任务', exact: true }).click()
  await expect(page.locator('.task-status')).toHaveText('已完成', { timeout: 30000 })
  await expect(page.locator('.task-progress')).toContainText('3 / 3')
  await page.getByRole('link', { name: '质量检查', exact: true }).click()
  await page.getByRole('tab', { name: '术语检查', exact: true }).click()
  await page.getByRole('button', { name: '开始检查', exact: true }).click()
  await expect(page.getByRole('link', { name: '校对此条', exact: true })).toHaveCount(1)
  await page.getByRole('link', { name: '校对此条', exact: true }).click()
  const highlighted = page.locator('.item-table-row.highlighted')
  await expect(highlighted).toContainText('Hello, world!')
  await highlighted.getByRole('button', { name: '编辑译文', exact: true }).click()
  await highlighted.getByRole('textbox', { name: '编辑译文', exact: true }).fill('你好，世界！')
  await highlighted.getByRole('button', { name: '保存', exact: true }).click()
  await expect(highlighted.getByRole('button', { name: '编辑译文', exact: true })).toHaveText('你好，世界！')
  await highlighted.getByRole('checkbox').check()
  await page.screenshot({ path: testInfo.outputPath('m4-proofreading.png'), fullPage: true })
  await page.getByRole('link', { name: '导出', exact: true }).click()
  await page.getByRole('textbox', { name: '输出文件夹', exact: true }).fill(output)
  await page.getByRole('button', { name: '保存项目缓存', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: '项目缓存已保存' })).toBeVisible()
  await page.getByRole('button', { name: '导出译文', exact: true }).click()
  await expect(page.getByRole('heading', { name: '导出完成', exact: true })).toBeVisible()
  const exported = await readFile(join(output, 'story_translated.txt'), 'utf8')
  // The unchanged Python TxtWriter writes the native platform newline.
  expect(exported).toBe(['你好，世界！', '这是一次无界面翻译测试。', '故事在这里继续。', ''].join(EOL))
  const bilingual = await readFile(join(output, 'bilingual_txt', 'story_bilingual.txt'), 'utf8')
  expect(bilingual).toBe([
    '你好，世界！', 'Hello, world!', '这是一次无界面翻译测试。', 'This is a headless translation test.',
    '故事在这里继续。', 'The story continues here.', '',
  ].join(EOL))
  await page.screenshot({ path: testInfo.outputPath('m4-export.png'), fullPage: true })
  await page.getByRole('button', { name: '打开日志', exact: true }).click()
  await expect(page.getByRole('region', { name: '运行日志', exact: true })).not.toContainText('e2e-private-key')
})
