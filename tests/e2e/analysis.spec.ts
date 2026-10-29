import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { test, expect } from '../../frontend/playwright-fixtures'

test.use({ mockProviders: true })

test('manually imports, edits, filters, moves, publishes and exports project analysis', async ({ page, backend }, testInfo) => {
  const source = join(backend.directory, 'analysis-input')
  await mkdir(source)
  await writeFile(join(source, 'story.txt'), 'Alice and Bob explore a new world.\n', 'utf8')
  await writeFile(join(backend.directory, 'data', 'config.json'), JSON.stringify({ source_language: 'english', target_language: 'chinese_simplified', translation_project: 'Txt' }), 'utf8')
  await page.goto(backend.handoff('/'))
  await page.getByRole('textbox', { name: '项目路径', exact: true }).fill(source)
  await page.getByRole('combobox', { name: '项目类型', exact: true }).selectOption('Txt')
  await page.getByRole('button', { name: '打开项目', exact: true }).click()
  await expect(page.getByRole('heading', { name: '项目概览', exact: true })).toBeVisible()
  await page.getByRole('link', { name: '项目分析', exact: true }).click()
  await expect(page.getByRole('heading', { name: '项目分析', exact: true })).toBeVisible()
  await page.locator('input[type="file"]').setInputFiles({
    name: 'characters.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify([
      { source: 'Alice', recommended_translation: '爱丽丝', gender: '女', occurrence_count: 4, note: '主角', regex: true, ignored_metadata: { keepOutOfExport: true } },
      { source: 'Bob', recommended_translation: '鲍勃', gender: '男', occurrence_count: 2, note: '伙伴' },
    ])),
  })
  await expect(page.getByRole('status').filter({ hasText: '已新增 2 条' })).toBeVisible()
  await page.getByRole('textbox', { name: '建议译文 1', exact: true }).fill('艾丽斯')
  await page.getByRole('button', { name: '保存修改', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: '修改已保存' })).toBeVisible()
  await page.getByRole('combobox', { name: '筛选分类', exact: true }).selectOption('女')
  await expect(page.getByRole('textbox', { name: '原文 2', exact: true })).toHaveCount(0)
  await page.getByRole('textbox', { name: '搜索分析结果', exact: true }).fill('Alice')
  await page.getByRole('checkbox', { name: '1', exact: true }).check()
  await page.getByRole('textbox', { name: '目标分类', exact: true }).fill('Identity')
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('button', { name: '移至术语', exact: true }).click()
  await page.getByRole('tab', { name: /^术语/ }).click()
  await expect(page.getByRole('textbox', { name: '原文 1', exact: true })).toHaveValue('Alice')
  await expect(page.getByRole('textbox', { name: '建议译文 1', exact: true })).toHaveValue('艾丽斯')
  await expect(page.getByRole('textbox', { name: '备注 1', exact: true })).toHaveValue('主角；原分类: 女')
  await page.getByRole('button', { name: '写入公共表格', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: '已追加 1 条' })).toBeVisible()
  const configuration = await backend.readConfig()
  expect(configuration.prompt_dictionary_tables).toEqual(expect.arrayContaining([expect.objectContaining({ rows: expect.arrayContaining([expect.objectContaining({ src: 'Alice', dst: '艾丽斯', regex: false })]) })]))
  await page.getByRole('combobox', { name: '筛选分类', exact: true }).selectOption('Identity')
  await page.getByRole('textbox', { name: '搜索分析结果', exact: true }).fill('Alice')
  const downloading = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出当前筛选', exact: true }).click()
  const download = await downloading
  expect(download.suggestedFilename()).toBe('analysis-terms.json')
  const filename = testInfo.outputPath('analysis-terms.json')
  await download.saveAs(filename)
  expect(JSON.parse(await readFile(filename, 'utf8'))).toEqual([{ source: 'Alice', recommended_translation: '艾丽斯', category_path: 'Identity', occurrence_count: 4, note: '主角；原分类: 女' }])
  await page.screenshot({ path: testInfo.outputPath('m4-analysis.png'), fullPage: true })
})
