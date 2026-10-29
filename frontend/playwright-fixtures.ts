import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test as base, expect } from '@playwright/test'
import type { components } from './src/api/generated/schema'

// This frontend-local helper resolves Playwright normally from its package.
// Specs in the repository-level tests/e2e directory import the helper instead
// of requiring a second node_modules installation at the repository root.
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const testToken = 'ainiee-m2-e2e-fixed-local-token'
const directoryPrefix = 'ainiee-m2-e2e-'

async function withTimeout<T>(promise: Promise<T>, milliseconds: number, message: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout>
  try {
    return await Promise.race([
      promise,
      new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error(message)), milliseconds) }),
    ])
  } finally {
    clearTimeout(timer!)
  }
}

export class BackendProcess {
  private child: ChildProcessWithoutNullStreams | null = null
  private exited: Promise<number | null> | null = null
  private output = ''
  port = 0

  private constructor(readonly directory: string, private readonly mockProviders: boolean) {}

  static async create(mockProviders = false) {
    const directory = await mkdtemp(join(tmpdir(), directoryPrefix))
    await mkdir(join(directory, 'data'))
    await writeFile(join(directory, 'data', 'config.json'), '{}', 'utf8')
    return new BackendProcess(directory, mockProviders)
  }

  get origin() { return `http://127.0.0.1:${this.port}` }
  diagnostics() { return this.output }

  handoff(path = '/') {
    return `${path}#${new URLSearchParams({ api: this.origin, token: testToken })}`
  }

  async start(port = 0) {
    if (this.child) throw new Error('Backend is already running')
    const python = process.env.AINIEE_TEST_PYTHON ?? join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
    const env = {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      AINIEE_ALLOW_MULTI_INSTANCE: '1',
      AINIEE_PORTABLE: '1',
      AINIEE_RESOURCE_DIR: join(root, 'Resource'),
      AINIEE_USER_DATA_DIR: join(this.directory, 'data'),
      AINIEE_CACHE_DIR: join(this.directory, 'cache'),
      AINIEE_PROJECT_CACHE_DIR: join(this.directory, 'projects'),
      AINIEE_TIKTOKEN_CACHE_DIR: join(this.directory, 'tiktoken'),
      AINIEE_LOG_DIR: join(this.directory, 'logs'),
      AINIEE_DOWNLOADS_DIR: join(this.directory, 'downloads'),
      AINIEE_DOCUMENTS_DIR: join(this.directory, 'documents'),
    }
    const entry = this.mockProviders ? join(root, 'tests', 'e2e', 'backend_fixture.py') : join(root, 'AiNiee.py')
    const child = spawn(python, [entry, '--port', String(port), '--token', testToken], {
      cwd: root, env, windowsHide: true, stdio: 'pipe',
    })
    this.child = child
    this.exited = new Promise((resolveExit) => child.once('close', resolveExit))
    const append = (chunk: Buffer) => { this.output = (this.output + chunk.toString('utf8')).slice(-40_000) }
    child.stderr.on('data', append)
    let pending = ''
    const ready = new Promise<number>((resolveReady, reject) => {
      child.once('error', reject)
      child.once('close', code => reject(new Error(`Backend exited before READY (${code}):\n${this.output}`)))
      child.stdout.on('data', (chunk: Buffer) => {
        append(chunk)
        pending += chunk.toString('utf8')
        const lines = pending.split('\n')
        pending = lines.pop() ?? ''
        for (const line of lines) {
          const match = /^READY (\d+)\s*$/.exec(line)
          if (match) resolveReady(Number(match[1]))
        }
      })
    })
    this.port = await withTimeout(ready, 60_000, `Backend did not become ready:\n${this.output}`)
    const health = await fetch(`${this.origin}/health`, { signal: AbortSignal.timeout(5_000) })
    if (!health.ok) throw new Error(`Health check failed with ${health.status}`)
  }

  async readConfig(): Promise<components['schemas']['ConfigDocument']> {
    const response = await fetch(`${this.origin}/api/v1/config`, {
      headers: { Authorization: `Bearer ${testToken}` }, signal: AbortSignal.timeout(5_000),
    })
    if (!response.ok) throw new Error(`Config read failed with ${response.status}`)
    return response.json()
  }

  async readPersistedConfig() {
    return JSON.parse(await readFile(join(this.directory, 'data', 'config.json'), 'utf8')) as Record<string, unknown>
  }

  async stop() {
    const child = this.child
    if (!child) return
    try {
      if (child.pid !== undefined && child.exitCode === null && child.signalCode === null) {
        try {
          await fetch(`${this.origin}/api/v1/shutdown`, {
            method: 'POST', headers: { Authorization: `Bearer ${testToken}` }, signal: AbortSignal.timeout(5_000),
          })
        } catch { /* A startup failure may never have opened a listener. */ }
        try {
          await withTimeout(this.exited!, 15_000, 'Backend did not shut down')
        } catch {
          child.kill()
          await withTimeout(this.exited!, 10_000, 'Unable to stop test backend')
        }
      }
    } finally {
      this.child = null
      this.exited = null
      child.stdout.destroy()
      child.stderr.destroy()
      child.stdin.destroy()
    }
  }

  async restart() {
    const port = this.port
    await this.stop()
    await this.start(port)
  }

  async dispose() {
    await this.stop()
    const directory = resolve(this.directory)
    if (dirname(directory) !== resolve(tmpdir()) || !basename(directory).startsWith(directoryPrefix)) {
      throw new Error('Refusing to remove an unexpected test directory')
    }
    await rm(directory, { recursive: true, force: true })
  }
}

export const test = base.extend<{ backend: BackendProcess; mockProviders: boolean }>({
  mockProviders: [false, { option: true }],
  backend: async ({ mockProviders }, use, testInfo) => {
    const backend = await BackendProcess.create(mockProviders)
    try {
      await backend.start()
      await use(backend)
    } finally {
      if (testInfo.status !== testInfo.expectedStatus) {
        await testInfo.attach('backend-log', { body: backend.diagnostics(), contentType: 'text/plain' })
      }
      await backend.dispose()
    }
  },
})

export { expect }
