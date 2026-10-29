import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { createServer } from 'node:net'
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

async function freeLoopbackPort(): Promise<number> {
  const server = createServer()
  return new Promise((resolvePort, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      if (!address || typeof address === 'string') { server.close(); reject(new Error('No loopback port was assigned')); return }
      server.close(error => error ? reject(error) : resolvePort(address.port))
    })
  })
}

export class BackendProcess {
  private child: ChildProcessWithoutNullStreams | null = null
  private exited: Promise<number | null> | null = null
  private output = ''
  port = 0

  private constructor(readonly directory: string, private readonly mockProviders: boolean, private readonly hostedFrontend: boolean) {}

  static async create(mockProviders = false, hostedFrontend = false) {
    if (process.env.AINIEE_TEST_EXECUTABLE && (!hostedFrontend || mockProviders)) {
      throw new Error('AINIEE_TEST_EXECUTABLE requires hostedFrontend and cannot be used with mockProviders')
    }
    const directory = await mkdtemp(join(tmpdir(), directoryPrefix))
    await mkdir(join(directory, 'data'))
    await writeFile(join(directory, 'data', 'config.json'), '{}', 'utf8')
    return new BackendProcess(directory, mockProviders, hostedFrontend)
  }

  get origin() { return `http://127.0.0.1:${this.port}` }
  diagnostics() { return this.output }

  handoff(path = '/') {
    const target = this.hostedFrontend ? new URL(path, this.origin).toString() : path
    return `${target}#${new URLSearchParams({ api: this.origin, token: testToken })}`
  }

  async start(port = 0) {
    if (this.child) throw new Error('Backend is already running')
    const executable = process.env.AINIEE_TEST_EXECUTABLE
    const python = process.env.AINIEE_TEST_PYTHON ?? join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
    const env: NodeJS.ProcessEnv = {
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
    // A frozen smoke test must obtain its resources from the package, even
    // when this fixture is run inside a checkout with usable source resources.
    if (executable) {
      delete env.AINIEE_RESOURCE_DIR
      delete env.PYTHONPATH
      delete env.PYTHONHOME
    }
    const listenPort = executable && port === 0 ? await freeLoopbackPort() : port
    this.port = listenPort
    const entry = this.mockProviders ? join(root, 'tests', 'e2e', 'backend_fixture.py') : join(root, 'AiNiee.py')
    const args = ['--port', String(listenPort), '--token', testToken, ...(this.hostedFrontend ? ['--web', '--no-browser'] : [])]
    const child = spawn(executable ? resolve(executable) : python, executable ? args : [entry, ...args], {
      cwd: executable ? this.directory : root, env, windowsHide: true, stdio: 'pipe',
    })
    this.child = child
    this.exited = new Promise((resolveExit) => child.once('close', resolveExit))
    const append = (chunk: Buffer) => { this.output = (this.output + chunk.toString('utf8')).slice(-40_000) }
    child.stderr.on('data', append)
    if (executable) {
      // Windowed executables intentionally have no stdout readiness protocol.
      // Poll the selected port and check authentication before using it.
      child.stdout.on('data', append)
      let spawnError: Error | null = null
      child.once('error', error => { spawnError = error })
      const deadline = Date.now() + 90_000
      while (Date.now() < deadline) {
        if (spawnError) throw spawnError
        if (child.exitCode !== null || child.signalCode !== null) throw new Error(`Packaged backend exited before health check (${child.exitCode}):\n${this.output}`)
        let health: Response | undefined
        try { health = await fetch(`${this.origin}/health`, { signal: AbortSignal.timeout(1000) }) }
        catch { /* The process may still be initializing its listener. */ }
        if (health?.ok) {
          const version = await fetch(`${this.origin}/api/v1/version`, { headers: { Authorization: `Bearer ${testToken}` }, signal: AbortSignal.timeout(1000) })
          if (!version.ok) throw new Error(`Packaged backend rejected the test token (${version.status})`)
          return
        }
        await new Promise(resolveWait => setTimeout(resolveWait, 100))
      }
      throw new Error(`Packaged backend did not become ready:\n${this.output}`)
    }
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

  async waitForExit(timeout = 30_000) {
    if (!this.exited) throw new Error('Backend has not been started')
    return withTimeout(this.exited, timeout, 'Backend did not finish shutting down')
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

export const test = base.extend<{ backend: BackendProcess; mockProviders: boolean; hostedFrontend: boolean }>({
  mockProviders: [false, { option: true }],
  hostedFrontend: [false, { option: true }],
  backend: async ({ mockProviders, hostedFrontend }, use, testInfo) => {
    const backend = await BackendProcess.create(mockProviders, hostedFrontend)
    try {
      await backend.start()
      await use(backend)
    } finally {
      if (testInfo.status !== testInfo.expectedStatus) {
        const fileLog = await readFile(join(backend.directory, 'logs', 'ainiee.log'), 'utf8').catch(() => '')
        await testInfo.attach('backend-log', { body: `${backend.diagnostics()}\n${fileLog.slice(-40_000)}`, contentType: 'text/plain' })
      }
      await backend.dispose()
    }
  },
})

export { expect }
