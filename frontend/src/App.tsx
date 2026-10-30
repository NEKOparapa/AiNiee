import { lazy, Suspense, useEffect, useState } from 'react'
import { Bot, ChevronRight, Folder, PlugZap, Search, X } from 'lucide-react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { AgentPanel } from '@/components/layout/AgentPanel'
import { ConnectionDialog } from '@/components/layout/ConnectionDialog'
import { TaskBar } from '@/components/layout/TaskBar'
import { Sidebar } from '@/components/layout/Sidebar'
import { WorkflowNavigation } from '@/components/layout/WorkflowNavigation'
import { ThemeController } from '@/components/layout/ThemeController'
import { useLayoutStore } from '@/stores/layout'
import { useUiContextStore } from '@/stores/ui-context'
import { useConnectionStore } from '@/stores/connection'
import { useBackendStore } from '@/stores/backend'
import { useBackendConnection } from '@/ws/use-backend-connection'
import { HomePage } from '@/workspaces/HomePage'
import { PlaceholderPage } from '@/workspaces/PlaceholderPage'
import { AppearancePage } from '@/workspaces/AppearancePage'
import { AboutPage } from '@/workspaces/AboutPage'
import { PageState } from '@/components/common/PageState'
import { LogContent, LogsPage } from '@/workspaces/LogsPage'
import { workspaces, workspaceForPath, type WorkspaceEntry } from '@/workspaces/registry'

const PlatformsPage = lazy(() => import('@/workspaces/platforms').then(module => ({ default: module.PlatformsPage })))
const OverviewPage = lazy(() => import('@/workspaces/projects/OverviewPage').then(module => ({ default: module.OverviewPage })))
const ItemsPage = lazy(() => import('@/workspaces/items/ItemsPage').then(module => ({ default: module.ItemsPage })))
const ChecksPage = lazy(() => import('@/workspaces/checks/ChecksPage').then(module => ({ default: module.ChecksPage })))
const ExportPage = lazy(() => import('@/workspaces/tasks/ExportPage').then(module => ({ default: module.ExportPage })))
const AnalysisPage = lazy(() => import('@/workspaces/analysis/AnalysisPage').then(module => ({ default: module.AnalysisPage })))
const PromptPage = lazy(() => import('@/workspaces/prompts/PromptPage').then(module => ({ default: module.PromptPage })))
const TablesPage = lazy(() => import('@/workspaces/tables/TablesPage').then(module => ({ default: module.TablesPage })))
const TaskSettingsPage = lazy(() => import('@/workspaces/settings').then(module => ({ default: module.TaskSettingsPage })))
const OutputSettingsPage = lazy(() => import('@/workspaces/settings').then(module => ({ default: module.OutputSettingsPage })))
const AdvancedSettingsPage = lazy(() => import('@/workspaces/settings').then(module => ({ default: module.AdvancedSettingsPage })))

export function App() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [connectionOpen, setConnectionOpen] = useState(false)
  const [logsOpen, setLogsOpen] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const collapsed = useLayoutStore(state => state.sidebarCollapsed)
  const toggleSidebar = useLayoutStore(state => state.toggleSidebar)
  const agentOpen = useLayoutStore(state => state.agentPanelOpen)
  const toggleAgent = useLayoutStore(state => state.toggleAgentPanel)
  const status = useConnectionStore(state => state.status)
  const connectionError = useConnectionStore(state => state.error)
  const project = useBackendStore(state => state.currentTask)
  const entry = workspaceForPath(location.pathname)
  useBackendConnection()

  useEffect(() => {
    const store = useUiContextStore.getState()
    store.setPage(entry?.id ?? 'home')
    store.setSelectedItemIds([])
    store.setFilters({})
    setSearch('')
    setMobileNavOpen(false)
  }, [entry?.id])
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (event.ctrlKey && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'l') {
        event.preventDefault()
        if (!event.repeat) toggleAgent()
      }
      if (event.key === 'Escape') { setSearch(''); setLogsOpen(false); setMobileNavOpen(false) }
    }
    window.addEventListener('keydown', keydown)
    return () => window.removeEventListener('keydown', keydown)
  }, [toggleAgent])
  const searchResults = workspaces.filter(item => t(`nav.${item.label}`).toLowerCase().includes(search.toLowerCase()))
  const renderWorkspace = (item: WorkspaceEntry) => {
    switch (item.kind) {
      case 'home': return <HomePage/>
      case 'platforms': return <Suspense fallback={<PageState/>}><PlatformsPage/></Suspense>
      case 'overview': return <Suspense fallback={<PageState/>}><OverviewPage/></Suspense>
      case 'items': return <Suspense fallback={<PageState/>}><ItemsPage/></Suspense>
      case 'checks': return <Suspense fallback={<PageState/>}><ChecksPage/></Suspense>
      case 'export': return <Suspense fallback={<PageState/>}><ExportPage/></Suspense>
      case 'analysis': return <Suspense fallback={<PageState/>}><AnalysisPage/></Suspense>
      case 'table': return <Suspense fallback={<PageState/>}><TablesPage key={item.id} name={item.id === 'glossary' ? 'glossary' : item.id === 'exclusion' ? 'exclusion' : item.id === 'replaceA' ? 'replace_a' : 'replace_b'}/></Suspense>
      case 'prompt': return <Suspense fallback={<PageState/>}><PromptPage key={item.id} kind={item.path === '/prompts/library' ? 'library' : item.path === '/prompts/system' ? 'system' : item.path === '/prompts/polish' ? 'polish' : item.path === '/prompts/world' ? 'world' : item.path === '/prompts/style' ? 'style' : item.path === '/prompts/examples' ? 'examples' : 'characters'}/></Suspense>
      case 'task': return <Suspense fallback={<PageState/>}><TaskSettingsPage/></Suspense>
      case 'output': return <Suspense fallback={<PageState/>}><OutputSettingsPage/></Suspense>
      case 'advanced': return <Suspense fallback={<PageState/>}><AdvancedSettingsPage/></Suspense>
      case 'appearance': return <AppearancePage openConnection={() => setConnectionOpen(true)}/>
      case 'logs': return <LogsPage/>
      case 'about': return <AboutPage/>
      default: return <PlaceholderPage entry={item}/>
    }
  }
  const handleToggleSidebar = () => {
    if (window.matchMedia('(max-width: 760px)').matches) setMobileNavOpen(value => !value)
    else toggleSidebar()
  }
  return <>
    <ThemeController/>
    <a href="#main-content" className="skip-link">{t('app.skip')}</a>
    <div className={`app-shell${collapsed ? ' nav-collapsed' : ''}${mobileNavOpen ? ' mobile-nav-open' : ''}`}>
      {mobileNavOpen && <button className="navigation-scrim" aria-label={t('app.collapse')} onClick={() => setMobileNavOpen(false)}/>}
      <Sidebar collapsed={collapsed} mobileOpen={mobileNavOpen} onToggle={handleToggleSidebar}
        onExpand={() => { if (window.matchMedia('(max-width: 760px)').matches) setMobileNavOpen(true); else if (collapsed) toggleSidebar() }} onNavigate={() => setMobileNavOpen(false)}/>
      <div className="app-main">
        <header className="topbar">
          <div className="project-heading"><Folder size={16}/><span>{project?.project_name || t('app.noProject')}</span><ChevronRight size={12}/><strong>{t(`nav.${entry?.label ?? 'home'}`)}</strong></div>
          <div className="topbar-tools">
            <div className="page-search"><Search size={15}/><input value={search} onChange={event => setSearch(event.target.value)} placeholder={t('app.search')} aria-label={t('app.search')}
              onKeyDown={event => { if (event.key === 'Enter' && searchResults[0]) navigate(searchResults[0].path) }}/>
              {search && <div className="search-results">{searchResults.length ? searchResults.map(item => <button key={item.id} onClick={() => navigate(item.path)}><item.icon size={15}/>{t(`nav.${item.label}`)}</button>) : <p>{t('app.noResults')}</p>}</div>}
            </div>
            <button className={`connection-pill ${status}`} onClick={() => setConnectionOpen(true)} title={connectionError ? t(connectionError) : t('connection.change')} aria-label={t('connection.change')}><span className="small-dot"/><span>{t(`connection.${status}`)}</span></button>
            <span className="topbar-separator"/>
            <Button variant={agentOpen ? 'secondary' : 'ghost'} size="icon" className="agent-toggle" onClick={toggleAgent} aria-label={t('agent.toggle')} aria-pressed={agentOpen} title={`${t('agent.toggle')} · Ctrl+L`}><Bot size={20}/></Button>
          </div>
        </header>
        <div className="app-surface">
          {connectionError && <div className="connection-error" role="alert"><PlugZap size={15}/><span>{t(connectionError)}</span><button onClick={() => setConnectionOpen(true)}>{t('connection.change')}</button></div>}
          <div className="workspace-stage">
            <div className="workspace-column">
              {entry?.group === 'project' && <WorkflowNavigation/>}
              <main id="main-content" tabIndex={-1} className="main-content"><Routes>
                {workspaces.map(item => <Route key={item.id} path={item.path} element={renderWorkspace(item)}/>)}
                <Route path="*" element={<Navigate to="/" replace/>}/>
              </Routes></main>
            </div>
            {agentOpen && <AgentPanel/>}
            {logsOpen && <section className="log-drawer" aria-label={t('task.logTitle')}><Button variant="ghost" size="icon" className="drawer-close" onClick={() => setLogsOpen(false)} aria-label={t('common.close')}><X size={17}/></Button><LogContent/></section>}
          </div>
          <TaskBar onOpenLogs={() => setLogsOpen(value => !value)}/>
        </div>
      </div>
    </div>
    <ConnectionDialog open={connectionOpen} onClose={() => setConnectionOpen(false)}/>
  </>
}
