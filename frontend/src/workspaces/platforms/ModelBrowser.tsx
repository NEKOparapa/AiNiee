import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LoaderCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { platformErrorCode, usePlatformModels, useUpdatePlatform, type Platform } from '@/api/platforms'
import { PlatformDialog } from './PlatformDialog'

export function ModelBrowser({ platform, onClose, onSaved }: { platform: Platform; onClose: () => void; onSaved: () => void }) {
  const { t } = useTranslation('platforms')
  const models = usePlatformModels()
  const update = useUpdatePlatform()
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const started = useRef(false)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const { mutate } = models
  useEffect(() => {
    // StrictMode runs effects twice; model discovery should make one request.
    if (!started.current) { started.current = true; mutate(platform.id) }
  }, [mutate, platform.id])
  const visible = models.data?.models.filter(model => model.toLowerCase().includes(search.toLowerCase())) ?? []
  const save = async () => {
    try {
      await update.mutateAsync({ id: platform.id, changes: {
        model_datas: [...new Set([...platform.model_datas, ...selected])],
        ...(selected.length === 1 ? { model: selected[0] } : {}),
      } })
      if (mounted.current) onSaved()
    } catch { /* Render a localized error without exposing response bodies. */ }
  }
  return <PlatformDialog title={`${t('modelBrowser')} · ${platform.name}`} onClose={onClose}>
    <div className="platform-dialog-body">
      <p className="platform-dialog-description">{t('modelChooseDetail')}</p>
      {models.isPending && <p role="status" className="platform-notice"><LoaderCircle className="animate-spin" size={16}/>{t('modelLoading')}</p>}
      {models.isError && <div role="alert"><p className="platform-error">{t(`errors.${platformErrorCode(models.error)}`, { defaultValue: t('errors.request_failed') })}</p>
        <Button variant="outline" onClick={() => models.mutate(platform.id)}><RefreshCw size={15}/>{t('retry')}</Button>
      </div>}
      {models.data && <>
        <Input value={search} onChange={event => setSearch(event.target.value)} aria-label={t('modelSearch')} placeholder={t('modelSearch')}/>
        <div className="platform-model-list">{visible.map(model => <label key={model} className="platform-model-option">
          <input type="checkbox" checked={selected.includes(model)} disabled={update.isPending} onChange={event => setSelected(previous => event.target.checked ? [...previous, model] : previous.filter(item => item !== model))}/>
          <span>{model}</span>
        </label>)}</div>
        {!visible.length && <p className="platform-dialog-description">{t(models.data.models.length ? 'modelNoMatch' : 'modelEmpty')}</p>}
        <p className="platform-dialog-description" role="status">{t('modelSelected', { count: selected.length })}</p>
      </>}
      {update.isError && <p role="alert" className="platform-error">{t(`errors.${platformErrorCode(update.error)}`, { defaultValue: t('errors.request_failed') })}</p>}
    </div>
    <footer className="platform-dialog-footer"><Button variant="outline" onClick={onClose}>{t('cancel')}</Button>
      <Button disabled={!selected.length || update.isPending} onClick={() => { void save() }}>{update.isPending && <LoaderCircle size={15} className="animate-spin"/>}{t(update.isPending ? 'saving' : 'modelSelect')}</Button>
    </footer>
  </PlatformDialog>
}
