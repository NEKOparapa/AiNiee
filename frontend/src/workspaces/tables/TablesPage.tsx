import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, ArrowRight, Download, Plus, Save, Trash2, Upload } from 'lucide-react'
import { type PublicTable, type TableCollection, type TableName, downloadTable, useExportTables, useSaveTables, useTables } from '@/api/tables'
import { useConnectionStore } from '@/stores/connection'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageState } from '@/components/common/PageState'
import { TableRowsEditor, tableColumns } from './TableRowsEditor'
import { TableFeedback } from './TableFeedback'
import { TableImportDialog } from './TableImportDialog'
import { EditorDialog } from './EditorDialog'
import './translations'
import './styles.css'

export function TablesPage({ name }: { name: TableName }) {
  const { t } = useTranslation('tables')
  const connection = useConnectionStore(s => s.connection)
  const revision = useConnectionStore(s => s.revision)
  const query = useTables(name)
  const save = useSaveTables(name)
  const download = useExportTables(name)
  const [draft, setDraft] = useState<TableCollection | null>(null)
  const [importing, setImporting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [format, setFormat] = useState<'json' | 'xlsx'>('json')
  useEffect(() => { setDraft(null); setImporting(false); setDeleting(false) }, [name, revision])
  const value = draft ?? query.data
  const table = value?.tables.find(item => item.id === value.active_table_id) ?? value?.tables[0]
  const index = value?.tables.findIndex(item => item.id === table?.id) ?? -1
  const modifyTable = (change: Partial<PublicTable>) => value && table && setDraft({ ...value, tables: value.tables.map(item => item.id === table.id ? { ...item, ...change } : item) })
  const create = () => {
    if (!value) return
    const id = crypto.randomUUID()
    setDraft({ tables: [...value.tables, { id, name: `${t('newTable')} ${value.tables.length + 1}`, enabled: true, rows: [] }], active_table_id: id })
  }
  const move = (offset: number) => {
    if (!value || index + offset < 0 || index + offset >= value.tables.length) return
    const tables = [...value.tables]; [tables[index], tables[index + offset]] = [tables[index + offset], tables[index]]
    setDraft({ ...value, tables })
  }
  return <div className="workspace table-workspace"><header className="page-heading"><div><h1>{t(name)}</h1><p>{t('subtitle')}</p></div><div className="table-actions">{draft ? <span className="table-save-status">{t('dirty')}</span> : save.isSuccess && <span role="status" className="table-save-status">{t('saved')}</span>}<Button disabled={!value || !connection || save.isPending} onClick={() => value && save.mutate(value, { onSuccess: () => { if (useConnectionStore.getState().revision === revision) setDraft(null) } })}><Save/>{t(save.isPending ? 'saving' : 'save')}</Button></div></header>
    {!connection ? <PageState disconnected/> : <><TableFeedback loading={query.isPending} error={query.error} retry={() => void query.refetch()}/><TableFeedback error={save.error ?? download.error}/>{value && <>
      {name !== 'characters' && <div className="table-tabs" role="tablist">{value.tables.map(item => <Button role="tab" disabled={save.isPending} variant="ghost" key={item.id} aria-selected={item.id === table?.id} onClick={() => setDraft({ ...value, active_table_id: item.id })}>{item.name}{!item.enabled && <span aria-hidden>○</span>}</Button>)}<Button variant="outline" onClick={create} disabled={save.isPending}><Plus/>{t('newTable')}</Button></div>}
      <div className="table-actions"><Button variant="outline" disabled={Boolean(draft) || save.isPending} onClick={() => setImporting(true)}><Upload/>{t('import')}</Button><select aria-label={t('export')} value={format} onChange={e => setFormat(e.target.value as 'json' | 'xlsx')}><option value="json">JSON</option><option value="xlsx">XLSX</option></select><Button variant="outline" disabled={Boolean(draft) || !table || download.isPending} onClick={() => table && download.mutate({ table_ids: [table.id], format }, { onSuccess: downloadTable })}><Download/>{t('export')}</Button>{name !== 'characters' && <Button variant="ghost" disabled={Boolean(draft) || !value.tables.length || download.isPending} onClick={() => download.mutate({ bundle: true, format }, { onSuccess: downloadTable })}>{t('exportAll')}</Button>}</div>
      {table ? <><section className="table-metadata">{name !== 'characters' && <Input aria-label={t('tableName')} value={table.name} disabled={save.isPending} onChange={e => modifyTable({ name: e.target.value })}/>}<label><input type="checkbox" checked={table.enabled ?? true} disabled={save.isPending} onChange={e => modifyTable({ enabled: e.target.checked })}/>{t('enabled')}</label>{name !== 'characters' && <><Button variant="ghost" size="icon" disabled={index === 0 || save.isPending} aria-label={t('moveUp')} onClick={() => move(-1)}><ArrowLeft/></Button><Button variant="ghost" size="icon" disabled={index === value.tables.length - 1 || save.isPending} aria-label={t('moveDown')} onClick={() => move(1)}><ArrowRight/></Button><Button variant="ghost" size="icon" disabled={save.isPending} aria-label={t('removeTable')} onClick={() => setDeleting(true)}><Trash2/></Button></>}{name === 'glossary' && <div className="table-match-options">{(['case_sensitive', 'whole_word', 'split_match'] as const).map(option => <label key={option}><input type="checkbox" disabled={save.isPending} checked={table.match_options?.[option] ?? false} onChange={e => modifyTable({ match_options: { ...table.match_options, [option]: e.target.checked } })}/>{t(option)}</label>)}</div>}</section><TableRowsEditor contextId={`${name}:${table.id}:${revision}`} rows={table.rows ?? []} columns={tableColumns[name]} disabled={save.isPending} onChange={rows => modifyTable({ rows })}/></> : <div className="table-empty">{t('noTable')}</div>}
    </>}</>}
    {importing && <TableImportDialog name={name} tableId={table?.id ?? null} onClose={() => setImporting(false)}/>}
    {deleting && table && value && <EditorDialog title={t('removeTable')} onClose={() => setDeleting(false)}><p>{t('removeConfirm', { name: table.name })}</p><footer><Button variant="outline" onClick={() => setDeleting(false)}>{t('cancel')}</Button><Button variant="destructive" onClick={() => { const tables = value.tables.filter(item => item.id !== table.id); setDraft({ tables, active_table_id: tables[0]?.id ?? null }); setDeleting(false) }}>{t('removeTable')}</Button></footer></EditorDialog>}
  </div>
}
