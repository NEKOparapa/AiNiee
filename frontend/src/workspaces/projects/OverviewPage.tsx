import { useEffect, useMemo, useState } from 'react'
import { ChevronRight, FileText, Folder, FolderOpen, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useCurrentProject, useProjectFiles, useProjectStats, type ProjectFile } from '@/api/projects'
import { useConnectionStore } from '@/stores/connection'
import { useUiContextStore } from '@/stores/ui-context'
import { PageState } from '@/components/common/PageState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ProjectFeedback } from './ProjectFeedback'
import './styles.css'

type TreeNode = { name: string; path: string; children: Map<string, TreeNode>; file?: ProjectFile }

function buildTree(files: ProjectFile[]) {
  const root: TreeNode = { name: '', path: '', children: new Map() }
  for (const file of files) {
    const parts = file.path.replaceAll('\\', '/').split('/').filter(Boolean)
    let node = root
    parts.forEach((name, index) => {
      const path = parts.slice(0, index + 1).join('/')
      if (!node.children.has(name)) node.children.set(name, { name, path, children: new Map() })
      node = node.children.get(name)!
      if (index === parts.length - 1) node.file = file
    })
  }
  return root
}

function FileTree({ node, selected, onSelect }: { node: TreeNode; selected: string; onSelect: (path: string) => void }) {
  return <ul className="project-tree">{Array.from(node.children.values()).map(child => <li key={child.path}>
    {child.file ? <button className={selected === child.file.path ? 'selected' : ''} onClick={() => onSelect(child.file!.path)} title={child.file.path} aria-pressed={selected === child.file.path}><FileText size={16}/><span>{child.name}</span><small>{child.file.item_count.toLocaleString()}</small></button>
      : <details open><summary><ChevronRight size={13}/><Folder size={16}/><span>{child.name}</span></summary><FileTree node={child} selected={selected} onSelect={onSelect}/></details>}
  </li>)}</ul>
}

export function OverviewPage() {
  const { t, i18n } = useTranslation('projects')
  const current = useCurrentProject()
  const project = current.data?.project
  const connection = useConnectionStore(s => s.connection)
  const files = useProjectFiles(Boolean(connection && project))
  const stats = useProjectStats(Boolean(connection && project))
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState('')
  useEffect(() => { setFilter(''); setSelected('') }, [project?.project_id])
  useEffect(() => {
    useUiContextStore.getState().setFilters({ file: selected, q: filter })
  }, [filter, selected])
  const visible = useMemo(() => (files.data ?? []).filter(file => file.path.toLocaleLowerCase().includes(filter.toLocaleLowerCase())), [files.data, filter])
  const tree = useMemo(() => buildTree(visible), [visible])
  const activeFile = files.data?.find(file => file.path === selected)
  const numbers = new Intl.NumberFormat(i18n.language)
  const done = (stats.data?.translated ?? 0) + (stats.data?.polished ?? 0)
  const total = stats.data?.total ?? 0
  const percent = total ? Math.min(100, Math.round(done * 100 / total)) : 0
  return <div className="workspace project-overview">
    <header className="page-heading"><div><h1>{t('overview')}</h1><p>{t('overviewDetail')}</p></div><Link className="project-text-link" to="/">{t('changeProject')}<ChevronRight size={15}/></Link></header>
    {!connection ? <PageState disconnected/> : current.isPending ? <ProjectFeedback loading/> : current.isError ? <ProjectFeedback error={current.error} retry={() => void current.refetch()}/> : !project ? <div className="project-empty-state"><FolderOpen size={42} strokeWidth={1.2}/><h2>{t('noProject')}</h2><p>{t('noProjectDetail')}</p><Button asChild><Link to="/">{t('toHome')}</Link></Button></div> : <>
      <section className="project-summary"><div className="project-summary-icon"><FolderOpen size={28} strokeWidth={1.5}/></div><div><span className="eyebrow">{t('current')}</span><h2>{project.project_name}</h2><p title={project.input_path}>{project.input_path}</p></div><span className="subtle-badge">{project.project_type === 'AutoType' ? t('autoType') : project.project_type}</span></section>
      <ProjectFeedback loading={stats.isPending} error={stats.error} retry={() => void stats.refetch()}/>
      {stats.data && <><div className="project-stat-grid">{([
        ['files', project.file_count], ['items', stats.data.total], ['translated', stats.data.translated], ['polished', stats.data.polished],
      ] as const).map(([name, value]) => <div className="project-stat" key={name}><span>{t(name)}</span><strong>{numbers.format(value)}</strong></div>)}</div>
        <section className="project-progress-card"><div><div><h3>{t('progress')}</h3><p>{t('progressDetail')}</p></div><strong>{percent}<small>%</small></strong></div><progress value={done} max={total || 1} aria-label={t('progress')}/><div className="project-status-counts">{(['untranslated', 'excluded', 'questionable', 'other'] as const).map(key => <span key={key}>{t(key)} <b>{numbers.format(stats.data[key])}</b></span>)}</div></section></>}
      <div className="project-files-grid"><section className="project-files-panel"><header><h2>{t('tree')}</h2><span>{t('fileCount', { count: visible.length })}</span></header><div className="project-file-filter"><Search size={15}/><Input value={filter} onChange={e => setFilter(e.target.value)} placeholder={t('searchFiles')} aria-label={t('searchFiles')}/></div>
        <ProjectFeedback loading={files.isPending} error={files.error} retry={() => void files.refetch()}/>
        {files.isSuccess && (visible.length ? <FileTree node={tree} selected={selected} onSelect={setSelected}/> : <p className="directory-empty">{t('noFiles')}</p>)}
      </section><section className="project-file-details"><h2>{t('fileDetails')}</h2>{!activeFile ? <div className="file-details-empty"><FileText size={30} strokeWidth={1.2}/><p>{t('pickFile')}</p></div> : <>
        <h3 className="selected-file-path">{activeFile.path}</h3><dl>{([
          ['projectType', activeFile.project_type], ['encoding', activeFile.encoding], ['items', activeFile.item_count], ['translated', activeFile.translated_count], ['polished', activeFile.polished_count], ['excluded', activeFile.excluded_count], ['questionable', activeFile.questionable_count],
        ] as const).map(([key, value]) => <div key={key}><dt>{t(key)}</dt><dd>{typeof value === 'number' ? numbers.format(value) : value}</dd></div>)}</dl>
        <h3>{t('language')}</h3>{activeFile.language_stats.length ? <ul className="language-stats">{activeFile.language_stats.map(stat => <li key={stat.language}><span>{stat.language}</span><b>{t('itemCount', { count: stat.count })}</b></li>)}</ul> : <p className="muted-detail">{t('languageEmpty')}</p>}
      </>}</section></div>
      {stats.data && <footer className="project-runtime-stats"><span>{t('tokens')} <b>{numbers.format(stats.data.progress.token ?? 0)}</b></span><span>{t('requests')} <b>{numbers.format(stats.data.progress.total_requests ?? 0)}</b></span><span>{t('elapsed')} <b>{numbers.format(Math.round(stats.data.progress.time ?? 0))}</b></span></footer>}
    </>}
  </div>
}
