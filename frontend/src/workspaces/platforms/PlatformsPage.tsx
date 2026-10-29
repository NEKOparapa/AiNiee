import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, Cloud, FlaskConical, Globe2, LoaderCircle, Pencil, Plus, Server, Settings2, Trash2, Workflow } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { PageHeading } from '@/components/common/PageHeading'
import { PageState } from '@/components/common/PageState'
import { useConnectionStore } from '@/stores/connection'
import { platformErrorCode, useDeletePlatform, usePlatforms, useSaveBindings, useTestPlatform, type Platform } from '@/api/platforms'
import { BindingsCard } from './BindingsCard'
import { PlatformDialog } from './PlatformDialog'
import { PlatformForm } from './PlatformForm'
import { ModelBrowser } from './ModelBrowser'
import './translations'
import './styles.css'

function publicHost(value: string): string {
  try { return new URL(value).host } catch { return '' }
}

function ConnectedPlatforms() {
  const { t } = useTranslation('platforms')
  const query = usePlatforms()
  const connected = useConnectionStore(state => state.connection !== null)
  const [editing, setEditing] = useState<Platform | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Platform | null>(null)
  const [browsing, setBrowsing] = useState<Platform | null>(null)
  const [testing, setTesting] = useState<Platform | null>(null)
  const [notice, setNotice] = useState('')
  const activate = useSaveBindings()
  const remove = useDeletePlatform()
  const test = useTestPlatform()
  const current = query.data?.platforms.find(platform => platform.id === query.data?.bindings.active)
  const testPlatform = (platform: Platform) => { setTesting(platform); test.mutate(platform.id) }
  const deletePlatform = async () => {
    if (!deleting) return
    const deletedId = deleting.id
    try { await remove.mutateAsync(deletedId); setDeleting(current => current?.id === deletedId ? null : current); setNotice('deleted') } catch { /* Shown in the dialog. */ }
  }
  const groups = [
    { id: 'local', icon: Server }, { id: 'online', icon: Cloud }, { id: 'custom', icon: Globe2 },
  ] as const
  return <section className="workspace platform-workspace">
    <div className="platform-heading"><PageHeading title={t('title')} subtitle={t('subtitle')}/>
      <Button disabled={!connected || !query.data || query.isError} onClick={() => { setEditing('new'); setNotice('') }}><Plus size={16}/>{t('add')}</Button>
    </div>
    {!connected ? <p className="platform-empty" role="status">{t('connectRequired')}</p> : query.isPending ? <PageState/> : query.isError || !query.data ? <PageState error retry={() => void query.refetch()}/> : <>
      <div className="platform-summary"><Workflow size={17}/><span>{t('active')}</span><strong>{current?.name ?? t('none')}</strong></div>
      {notice && <p className="platform-notice" role="status"><Check size={15}/>{t(notice)}</p>}
      {activate.isError && <p className="platform-error" role="alert">{t(`errors.${platformErrorCode(activate.error)}`, { defaultValue: t('errors.request_failed') })}</p>}
      {!query.data.platforms.length ? <div className="platform-empty"><Workflow size={36} strokeWidth={1.4}/><h2>{t('empty')}</h2><p>{t('emptyDetail')}</p>
        <Button variant="outline" onClick={() => setEditing('new')}><Plus size={16}/>{t('add')}</Button>
      </div> : groups.map(group => {
        const items = query.data.platforms.filter(platform => (['local', 'online'].includes(platform.group) ? platform.group : 'custom') === group.id)
        if (!items.length) return null
        return <section className="platform-group" key={group.id} aria-label={t(`groups.${group.id}`)}>
          <div className="platform-group-heading"><group.icon size={19}/><div><h2>{t(`groups.${group.id}`)}</h2><p>{t(`groupDetail.${group.id}`)}</p></div></div>
          <div className="platform-grid">{items.map(platform => <article className={`platform-card${platform.id === current?.id ? ' is-active' : ''}`} key={platform.id} aria-label={platform.name}>
            <header className="platform-card-header"><span className="card-symbol"><group.icon size={21}/></span><div><h3>{platform.name}</h3><p>{platform.api_format}</p></div>
              {platform.id === current?.id && <span className="subtle-badge">{t('activated')}</span>}
            </header>
            <p className="platform-model">{platform.model}</p><p className="platform-host">{publicHost(platform.api_url)}</p>
            <div className="platform-card-actions">
              <Button variant="ghost" size="sm" onClick={() => setEditing(platform)}><Pencil size={14}/>{t('edit')}</Button>
              <Button variant="ghost" size="sm" disabled={test.isPending} onClick={() => testPlatform(platform)}>{test.isPending && test.variables === platform.id ? <LoaderCircle size={14} className="animate-spin"/> : <FlaskConical size={14}/>}{t(test.isPending && test.variables === platform.id ? 'testing' : 'test')}</Button>
              <Button variant="ghost" size="sm" onClick={() => setBrowsing(platform)}><Settings2 size={14}/>{t('models')}</Button>
              <Button variant="ghost" size="icon-sm" aria-label={`${t('remove')} ${platform.name}`} onClick={() => { remove.reset(); setDeleting(platform) }}><Trash2 size={14}/></Button>
            </div>
            {platform.id !== current?.id && <Button className="platform-active-button" variant="outline" disabled={activate.isPending}
              onClick={() => { activate.mutate({ ...query.data.bindings, active: platform.id }); setNotice('') }}>{t('activate')}</Button>}
          </article>)}</div>
        </section>
      })}
      <BindingsCard key={JSON.stringify(query.data.bindings)} platforms={query.data.platforms} bindings={query.data.bindings}/>
      {editing && <PlatformForm platform={editing === 'new' ? undefined : editing} presets={query.data.presets}
        onClose={() => setEditing(null)} onSaved={() => { setEditing(null); setNotice('saved') }}/ >}
      {browsing && <ModelBrowser platform={browsing} onClose={() => setBrowsing(null)} onSaved={() => { setBrowsing(null); setNotice('modelsSaved') }}/ >}
    </>}
    {deleting && <PlatformDialog title={t('removeTitle')} onClose={() => setDeleting(null)}>
      <div className="platform-dialog-body"><p className="platform-dialog-description">{t('removeDetail', { name: deleting.name })}</p>
        {remove.isError && <p className="platform-error" role="alert">{t(`errors.${platformErrorCode(remove.error)}`, { defaultValue: t('errors.request_failed') })}</p>}
      </div><footer className="platform-dialog-footer"><Button variant="outline" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
        <Button variant="destructive" disabled={remove.isPending} onClick={() => { void deletePlatform() }}>{t('remove')}</Button>
      </footer>
    </PlatformDialog>}
    {testing && <PlatformDialog title={`${t('testTitle')} · ${testing.name}`} onClose={() => setTesting(null)}>
      <div className="platform-dialog-body">
        {test.isPending && <p className="platform-notice" role="status"><LoaderCircle size={16} className="animate-spin"/>{t('testing')}</p>}
        {test.isError && <div role="alert"><p className="platform-error">{t(`errors.${platformErrorCode(test.error)}`, { defaultValue: t('errors.request_failed') })}</p>
          <Button variant="outline" onClick={() => test.mutate(testing.id)}>{t('retry')}</Button>
        </div>}
        {test.data && <><p role="status">{t('testSummary', { success: test.data.success_count, failure: test.data.failure_count })}</p>
          <ul className="platform-test-results">{test.data.results.map(result => <li key={result.key_index}><span>{t('testKey', { index: result.key_index })}</span><span className={result.success ? 'passed' : 'failed'}>{t(result.success ? 'testPassed' : 'testFailed')}</span></li>)}</ul>
        </>}
      </div><footer className="platform-dialog-footer"><Button variant="outline" onClick={() => setTesting(null)}>{t('close')}</Button></footer>
    </PlatformDialog>}
  </section>
}

export function PlatformsPage() {
  const revision = useConnectionStore(state => state.revision)
  return <ConnectedPlatforms key={revision}/>
}
