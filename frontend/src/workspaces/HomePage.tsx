import { useEffect, useState, type DragEvent } from 'react'
import { ArrowRight, FolderOpen, LoaderCircle, Workflow } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import { useConfig, usePatchConfig } from '@/api/config'
import { projectKeys, useCurrentProject, useOpenProject } from '@/api/projects'
import { useConnectionStore } from '@/stores/connection'
import { PageHeading } from '@/components/common/PageHeading'
import { PageState } from '@/components/common/PageState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DirectoryBrowser } from './projects/DirectoryBrowser'
import { ProjectFeedback } from './projects/ProjectFeedback'
import { ProjectHistory } from './projects/ProjectHistory'
import './projects/translations'
import './projects/styles.css'

export function droppedPath(data: DataTransfer): string | null {
  const uri = data.getData('text/uri-list').split(/\r?\n/).find(line => line && !line.startsWith('#'))
  if (uri) {
    try {
      const value = new URL(uri)
      if (value.protocol === 'file:' && (!value.hostname || value.hostname === 'localhost')) {
        return decodeURIComponent(value.pathname).replace(/^\/(?=[a-z]:\/)/i, '')
      }
    } catch { /* Fall through to a textual absolute path. */ }
  }
  const text = data.getData('text/plain').trim().replace(/^"(.*)"$/, '$1')
  return /^(?:[a-z]:[\\/]|\\\\|\/)/i.test(text) ? text : null
}

export function HomePage() {
  const { t } = useTranslation('projects')
  const navigate = useNavigate()
  const client = useQueryClient()
  const current = useCurrentProject()
  const config = useConfig()
  const saveConfig = usePatchConfig()
  const open = useOpenProject()
  const connection = useConnectionStore(s => s.connection)
  const revision = useConnectionStore(s => s.revision)
  const [path, setPath] = useState('')
  const [dirtyPath, setDirtyPath] = useState(false)
  const [browsing, setBrowsing] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [dropNotice, setDropNotice] = useState(false)
  useEffect(() => { setDirtyPath(false); setPath(''); setBrowsing(false); setDragging(false); setDropNotice(false) }, [revision])
  useEffect(() => {
    if (!dirtyPath && current.data) setPath(current.data.configured_path)
  }, [current.data, dirtyPath])
  const selectedType = config.data?.translation_project ?? current.data?.selected_project_type ?? 'AutoType'
  const types = current.data?.supported_project_types ?? []
  const pending = open.isPending || saveConfig.isPending
  const changeType = async (type: string) => {
    try {
      await saveConfig.mutateAsync({ translation_project: type })
      await client.invalidateQueries({ queryKey: projectKeys.current(revision) })
    } catch { /* The feedback below shows the failed selection. */ }
  }
  const openPath = async (value: string) => {
    try {
      await open.mutateAsync({ path: value.trim() })
      if (useConnectionStore.getState().revision === revision) navigate('/project')
    } catch { /* Preserve the path and show the application error. */ }
  }
  const onDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault(); setDragging(false)
    if (pending) return
    const fullPath = droppedPath(event.dataTransfer)
    if (fullPath) { setPath(fullPath); setDirtyPath(true); setDropNotice(false) }
    else setDropNotice(true)
  }
  return <div className="workspace home-page">
    <PageHeading title={t('title')} subtitle={t('intro')}/>
    {!connection ? <PageState disconnected/> : current.isPending ? <ProjectFeedback loading/> : current.isError ? <ProjectFeedback error={current.error} retry={() => void current.refetch()}/> : <>
        <section className="setting-card project-type-card"><div className="setting-copy"><h3><label htmlFor="project-type">{t('type')}</label></h3><p>{t('typeDetail')}</p></div><select id="project-type" className="select-control" value={selectedType} disabled={pending || config.isPending} onChange={e => void changeType(e.target.value)}>
          {!types.includes(selectedType) && <option value={selectedType}>{selectedType === 'AutoType' ? t('autoType') : selectedType}</option>}
          {types.map(type => <option value={type} key={type}>{type === 'AutoType' ? t('autoType') : type}</option>)}
        </select></section>
      <section className={`project-open-card${dragging ? ' drag-active' : ''}`} onDragOver={e => { e.preventDefault(); setDragging(true) }} onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false) }} onDrop={onDrop} aria-label={t('openTitle')}>
        <div className="project-open-heading"><span className="project-drop-icon"><FolderOpen size={44} strokeWidth={1.2}/></span><div><h2>{t('openTitle')}</h2><p>{t('openDetail')}</p></div></div>
        <form onSubmit={e => { e.preventDefault(); void openPath(path) }}>
          <label htmlFor="project-path">{t('path')}</label><div className="project-path-row"><Input id="project-path" placeholder={t('pathPlaceholder')} value={path} disabled={pending} onChange={e => { setPath(e.target.value); setDirtyPath(true); setDropNotice(false) }}/><Button type="button" variant="outline" disabled={pending} onClick={() => setBrowsing(true)}><FolderOpen size={16}/>{t('browse')}</Button></div>
          {dropNotice && <p className="project-feedback" role="status">{t('dropUnavailable')}</p>}
          <ProjectFeedback error={open.error ?? saveConfig.error}/><ProjectFeedback error={config.error} retry={() => void config.refetch()}/>
          <div className="project-open-footer"><p>{t('dropHint')}</p><Button type="submit" disabled={pending || !path.trim()}>{open.isPending ? <LoaderCircle size={16} className="animate-spin"/> : <ArrowRight size={16}/>} {t(open.isPending ? 'opening' : 'open')}</Button></div>
        </form>
      </section>
      <div className="project-home-links"><Link className="project-text-link" to="/platforms"><Workflow size={15}/>{t('platformLink')}</Link>{current.data?.project && <Link className="project-text-link" to="/project">{current.data.project.project_name}<ArrowRight size={15}/></Link>}</div>
      <ProjectHistory currentId={current.data?.project?.project_id} pending={pending} onContinue={value => void openPath(value)}/>
    </>}
    {browsing && <DirectoryBrowser initialPath={path} onSelect={value => { setPath(value); setDirtyPath(true); setDropNotice(false) }} onClose={() => setBrowsing(false)}/ >}
  </div>
}
