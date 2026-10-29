import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { type TableName, type TableImportRequest, useImportTables } from '@/api/tables'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { EditorDialog } from './EditorDialog'
import { TableFeedback } from './TableFeedback'

export function TableImportDialog({ name, tableId, onClose }: { name: TableName; tableId: string | null; onClose: () => void }) {
  const { t } = useTranslation('tables')
  const action = useImportTables(name)
  const [request, setRequest] = useState<TableImportRequest | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [mode, setMode] = useState<'new' | 'merge'>(name === 'characters' ? 'merge' : 'new')
  const [error, setError] = useState<unknown>(null)
  const load = async (file: File | undefined) => {
    if (!file) return
    setError(null); setRequest(null)
    if (file.size > 20 * 1024 * 1024) { setError(new ApiError(413, 'table_file_too_large')); return }
    try {
      const content_base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
        reader.onerror = () => reject(reader.error)
        reader.readAsDataURL(file)
      })
      const next = { filename: file.name, content_base64 }
      const preview = await action.mutateAsync({ ...next, preview: true })
      setRequest(next); setSelected(preview.tables.map(table => table.id))
    } catch (reason) { setError(reason) }
  }
  return <EditorDialog title={t('import')} onClose={onClose}><p>{t('importHint')}</p><label>{t('importPick')}<input type="file" accept=".json,.xlsx" disabled={action.isPending} onChange={e => void load(e.target.files?.[0])}/></label><div className="table-actions"><select aria-label={t('import')} value={mode} disabled={name === 'characters'} onChange={e => setMode(e.target.value as 'new' | 'merge')}><option value="new">{t('importNew')}</option><option value="merge" disabled={!tableId}>{t('importMerge')}</option></select></div><TableFeedback loading={action.isPending} error={error ?? action.error}/>{request && action.data && <section><h3>{t('preview')}</h3>{action.data.tables.map(table => <label className="table-import-entry" key={table.id}><input type="checkbox" checked={selected.includes(table.id)} onChange={e => setSelected(values => e.target.checked ? [...values, table.id] : values.filter(id => id !== table.id))}/><span>{table.name}</span><small>{t('rowCount', { count: table.rows?.length ?? 0 })}</small></label>)}</section>}<footer><Button variant="outline" onClick={onClose}>{t('cancel')}</Button><Button disabled={!request || !selected.length || action.isPending || (mode === 'merge' && !tableId)} onClick={() => request && action.mutate({ ...request, mode, selected_table_ids: selected, target_table_id: mode === 'merge' ? tableId : null }, { onSuccess: onClose })}>{t('confirmImport')}</Button></footer></EditorDialog>
}
