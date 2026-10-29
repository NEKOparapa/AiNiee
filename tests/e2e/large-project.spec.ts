import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { test, expect } from '../../frontend/playwright-fixtures'
import type { components } from '../../frontend/src/api/generated/schema'

test.use({ mockProviders: true })

test('keeps a real 50,000-item project responsive while paging, scrolling, filtering and editing', async ({ page, backend }, testInfo) => {
  test.setTimeout(180_000)
  const source = join(backend.directory, 'large-source')
  await mkdir(source)
  await writeFile(join(source, 'large.txt'), Array.from({ length: 50000 }, (_, index) => `Large project source ${String(index + 1).padStart(5, '0')}.`).join('\n') + '\n', 'utf8')
  const timings: Record<string, number> = {}
  await page.goto(backend.handoff('/'))
  await page.getByRole('textbox', { name: '项目路径', exact: true }).fill(source)
  await page.getByRole('combobox', { name: '项目类型', exact: true }).selectOption('Txt')
  let started = performance.now()
  await page.getByRole('button', { name: '打开项目', exact: true }).click()
  await expect(page.getByRole('heading', { name: '项目概览', exact: true })).toBeVisible({ timeout: 90_000 })
  timings.openProjectMs = Math.round(performance.now() - started)

  started = performance.now()
  const firstResponse = page.waitForResponse(response => response.url().includes('/api/v1/projects/current/items?') && response.ok())
  await page.getByRole('link', { name: '条目校对', exact: true }).click()
  const first: components['schemas']['ItemListResponse'] = await (await firstResponse).json()
  await expect(page.getByText('Large project source 00001.', { exact: true })).toBeVisible()
  timings.firstPageMs = Math.round(performance.now() - started)
  expect(first.total).toBe(50000)
  expect(first.items).toHaveLength(100)
  await expect(page.locator('.items-pagination')).toContainText('第 1 / 500 页 · 共 50000 条')
  expect(await page.locator('.item-table-row').count()).toBeLessThan(20)

  const scrollMetrics = await page.locator('.item-table-scroll').evaluate(async element => {
    const intervals: number[] = []
    let previous = performance.now()
    let maxRows = 0
    const maximum = element.scrollHeight - element.clientHeight
    for (let frame = 0; frame < 48; frame++) {
      element.scrollTop = maximum * (frame % 24) / 23
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
      const now = performance.now()
      intervals.push(now - previous)
      previous = now
      maxRows = Math.max(maxRows, element.querySelectorAll('.item-table-row').length)
    }
    intervals.sort((left, right) => left - right)
    return { maxRows, p95FrameMs: intervals[Math.floor(intervals.length * 0.95)], maxFrameMs: intervals.at(-1) ?? 0 }
  })
  expect(scrollMetrics.maxRows).toBeLessThan(20)
  // This is a regression guard for noticeable UI stalls, not a hardware FPS claim.
  expect(scrollMetrics.p95FrameMs).toBeLessThan(200)
  await expect(page.getByText('Large project source 00100.', { exact: true })).toBeVisible()

  started = performance.now()
  await page.getByRole('button', { name: '最后一页', exact: true }).click()
  await expect(page.getByText('Large project source 49901.', { exact: true })).toBeVisible()
  timings.lastPageMs = Math.round(performance.now() - started)
  await expect(page.locator('.items-pagination')).toContainText('第 500 / 500 页')
  await page.locator('.item-table-scroll').evaluate(element => { element.scrollTop = element.scrollHeight })
  await expect(page.getByText('Large project source 50000.', { exact: true })).toBeVisible()
  expect(await page.locator('.item-table-row').count()).toBeLessThan(20)

  started = performance.now()
  await page.getByRole('textbox', { name: '搜索原文与译文', exact: true }).fill('source 50000')
  await page.getByRole('button', { name: '筛选', exact: true }).click()
  await expect(page.locator('.items-pagination')).toContainText('共 1 条')
  const row = page.locator('.item-table-row')
  await expect(row).toHaveCount(1)
  await expect(row).toContainText('Large project source 50000.')
  timings.searchMs = Math.round(performance.now() - started)
  await row.getByRole('checkbox').check()
  await expect(page.locator('.items-toolbar')).toContainText('已选 1 条')

  started = performance.now()
  await row.getByRole('button', { name: '编辑译文', exact: true }).click()
  await row.getByRole('textbox', { name: '编辑译文', exact: true }).fill('第五万条人工校对译文。')
  await row.getByRole('button', { name: '保存', exact: true }).click()
  await expect(row.getByRole('button', { name: '编辑译文', exact: true })).toHaveText('第五万条人工校对译文。')
  timings.editAndPersistMs = Math.round(performance.now() - started)
  await page.reload()
  await expect(page.getByRole('button', { name: '编辑译文', exact: true })).toHaveText('第五万条人工校对译文。')
  await page.getByRole('button', { name: '重置', exact: true }).click()
  await expect(page.locator('.items-pagination')).toContainText('第 1 / 500 页')
  await expect(page.getByText('Large project source 00001.', { exact: true })).toBeVisible()

  expect(timings.firstPageMs).toBeLessThan(5000)
  expect(timings.lastPageMs).toBeLessThan(5000)
  expect(timings.searchMs).toBeLessThan(5000)
  expect(timings.editAndPersistMs).toBeLessThan(10000)
  const metrics = { items: 50000, pageSize: first.size, ...timings, ...scrollMetrics }
  await testInfo.attach('large-project-performance', { body: JSON.stringify(metrics, null, 2), contentType: 'application/json' })
  await writeFile(testInfo.outputPath('large-project-performance.json'), JSON.stringify(metrics, null, 2), 'utf8')
  await page.screenshot({ path: testInfo.outputPath('m5-large-project.png'), fullPage: true })
})
