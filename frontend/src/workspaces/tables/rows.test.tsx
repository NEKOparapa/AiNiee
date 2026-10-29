import { useState } from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import i18n from '@/i18n'
import { useUiContextStore } from '@/stores/ui-context'
import { TableRowsEditor, tableColumns, type EditorRow } from './TableRowsEditor'

beforeEach(async () => { await i18n.changeLanguage('zh-CN'); useUiContextStore.getState().setSelectedItemIds([]) })

it('edits the correct filtered row and preserves metadata while syncing selection context', () => {
  const changed = vi.fn()
  const initial: EditorRow[] = [{ src: 'alpha', dst: '一', origin: { file: 'a.txt' } }, { src: 'beta', dst: '二', origin: { file: 'b.txt' } }]
  render(<TableRowsEditor rows={initial} columns={tableColumns.glossary} contextId="glossary:one" onChange={changed}/>)
  fireEvent.change(screen.getByRole('textbox', { name: '筛选条目' }), { target: { value: 'beta' } })
  fireEvent.change(screen.getByRole('textbox', { name: '译文 2' }), { target: { value: 'Edited' } })
  expect(changed.mock.calls[0][0]).toEqual([initial[0], { ...initial[1], dst: 'Edited' }])
  fireEvent.click(screen.getByRole('checkbox', { name: '2' }))
  expect(useUiContextStore.getState().selectedItemIds).toEqual(['glossary:one:1'])
  expect(useUiContextStore.getState().filters).toEqual({ table: 'glossary:one', q: 'beta' })
})

it('bounds rendered rows and deletes the selected rows across pagination', () => {
  function Harness() {
    const [rows, setRows] = useState<EditorRow[]>(Array.from({ length: 120 }, (_, index) => ({ src: `source ${index}` })))
    return <TableRowsEditor rows={rows} columns={tableColumns.exclusion} contextId="example" onChange={setRows}/>
  }
  render(<Harness/>)
  expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(51)
  fireEvent.click(screen.getByRole('checkbox', { name: '1' }))
  fireEvent.click(screen.getByRole('button', { name: '下一页' }))
  fireEvent.click(screen.getByRole('checkbox', { name: '51' }))
  fireEvent.click(screen.getByRole('button', { name: '删除选中' }))
  expect(screen.getByText('118 条')).toBeInTheDocument()
  expect(useUiContextStore.getState().selectedItemIds).toEqual([])
})
