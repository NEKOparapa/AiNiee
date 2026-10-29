import { test, expect } from '../../frontend/playwright-fixtures'

test.use({ hostedFrontend: true })

test('serves the built workbench on the backend origin and accepts a graceful exit', async ({ page, backend }, testInfo) => {
  test.setTimeout(180_000)
  await page.clock.install()
  const requests: { url: string; method: string }[] = []
  const sockets: string[] = []
  page.on('request', request => requests.push({ url: request.url(), method: request.method() }))
  page.on('websocket', socket => sockets.push(socket.url()))
  await page.route('**/*', route => new URL(route.request().url()).origin === backend.origin ? route.continue() : route.abort())

  await page.goto(backend.handoff('/settings/task'))
  await expect(page.getByRole('heading', { name: '任务设置', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '连接设置', exact: true }).filter({ hasText: '服务已连接' })).toBeVisible()
  expect(new URL(page.url()).origin).toBe(backend.origin)
  expect(new URL(page.url()).hash).toBe('')
  expect(await page.evaluate(() => localStorage.getItem('ainiee.connection'))).toBeNull()
  expect(await page.evaluate(() => sessionStorage.getItem('ainiee.connection'))).not.toBeNull()
  expect(requests.some(request => new URL(request.url).pathname.startsWith('/assets/'))).toBe(true)
  expect(requests.every(request => new URL(request.url).origin === backend.origin)).toBe(true)
  expect(requests.every(request => !new URL(request.url).searchParams.has('token'))).toBe(true)

  await page.getByRole('combobox', { name: '任务切分模式' }).selectOption('lines')
  const lines = page.getByRole('spinbutton', { name: '任务的文本行数', exact: true })
  await lines.fill('43')
  await lines.press('Tab')
  await expect.poll(async () => (await backend.readConfig()).lines_limit).toBe(43)
  await page.reload()
  await expect(page.getByRole('spinbutton', { name: '任务的文本行数', exact: true })).toHaveValue('43')
  expect(new URL(page.url()).pathname).toBe('/settings/task')
  expect(await backend.readPersistedConfig()).toMatchObject({ lines_limit: 43, lines_limit_switch: true })
  expect((await page.request.get(`${backend.origin}/api/v1/version`)).status()).toBe(401)

  await page.getByRole('link', { name: '关于 / 更新', exact: true }).click()
  await expect(page.getByRole('heading', { name: '关于 AiNiee', exact: true })).toBeVisible()
  page.once('dialog', dialog => dialog.dismiss())
  await page.getByRole('button', { name: '退出应用', exact: true }).click()
  expect(requests.filter(request => request.method === 'POST' && request.url.endsWith('/api/v1/shutdown'))).toHaveLength(0)

  page.once('dialog', dialog => dialog.accept())
  const accepted = page.waitForResponse(response => response.url() === `${backend.origin}/api/v1/shutdown` && response.status() === 202)
  await page.getByRole('button', { name: '退出应用', exact: true }).click()
  await accepted
  await expect(page.getByRole('status').filter({ hasText: '退出请求已接受' })).toBeVisible()
  await expect(page.getByRole('button', { name: '退出应用', exact: true })).toBeDisabled()
  expect(await page.evaluate(() => sessionStorage.getItem('ainiee.connection'))).toBeNull()
  // A 202 or a closed socket is not evidence that final persistence finished.
  // Observe the owned process exiting before checking the final cache on disk.
  expect(await backend.waitForExit()).toBe(0)
  expect(await backend.readPersistedConfig()).toMatchObject({ lines_limit: 43 })
  const socketCountAfterExit = sockets.length
  await page.clock.fastForward(30_000)
  expect(sockets).toHaveLength(socketCountAfterExit)
  await expect(page.getByRole('button', { name: '连接设置', exact: true })).toContainText('服务未连接')
  expect(requests.filter(request => request.method === 'POST' && request.url.endsWith('/api/v1/shutdown'))).toHaveLength(1)
  await page.screenshot({ path: testInfo.outputPath('m6-hosted-workbench.png'), fullPage: true })
})
