import { readFile } from 'node:fs/promises'
import openapiTS, { astToString } from 'openapi-typescript'

const expected = astToString(await openapiTS(new URL('../../backend/openapi.json', import.meta.url), { defaultNonNullable: false }))
const actual = await readFile(new URL('../src/api/generated/schema.d.ts', import.meta.url), 'utf8')
const normalize = value => value.replace(/\r\n/g, '\n').replace(/^\/\*\*[\s\S]*?\*\/\s*/, '').trim()
if (normalize(expected) !== normalize(actual)) {
  console.error('API types are stale. Run npm run generate:api after exporting the backend schema.')
  process.exitCode = 1
}
