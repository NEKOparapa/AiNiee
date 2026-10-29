import { lazy, Suspense, useEffect, useState } from 'react'
import { Bot, ChevronRight, Folder, Menu, PanelLeftClose, PlugZap, Search, X } from 'lucide-react'
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { AgentPanel } from '@/components/layout/AgentPanel'
import { ConnectionDialog } from '@/components/layout/ConnectionDialog'
import { TaskBar } from '@/components/layout/TaskBar'
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
import { TaskSettingsPage, OutputSettingsPage, AdvancedSettingsPage } from '@/workspaces/settings'
import { workspaces, workspaceGroups, workspaceForPath, type WorkspaceEntry } from '@/workspaces/registry'

const PlatformsPage = lazy(() => import('@/workspaces/platforms').then(module => ({ default: module.PlatformsPage })))
const OverviewPage = lazy(() => import('@/workspaces/projects/OverviewPage').then(module => ({ default: module.OverviewPage })))

export function App() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [connectionOpen, setConnectionOpen] = useState(false)
  const [logsOpen, setLogsOpen] = useState(false)
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
  }, [entry?.id])
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (event.ctrlKey && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'l') {
        event.preventDefault()
        if (!event.repeat) toggleAgent()
      }
      if (event.key === 'Escape') { setSearch(''); setLogsOpen(false) }
    }
    window.addEventListener('keydown', keydown)
    return () => window.removeEventListener('keydown', keydown)
  }, [toggleAgent])
  const navItem = (item: WorkspaceEntry) => <NavLink key={item.id} to={item.path} end title={t(`nav.${item.label}`)} className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}><item.icon size={17} strokeWidth={1.65}/><span className="nav-text">{t(`nav.${item.label}`)}</span></NavLink>
  const searchResults = workspaces.filter(item => t(`nav.${item.label}`).toLowerCase().includes(search.toLowerCase()))
  const renderWorkspace = (item: WorkspaceEntry) => {
    switch (item.kind) {
      case 'home': return <HomePage/>
      case 'platforms': return <Suspense fallback={<PageState/>}><PlatformsPage/></Suspense>
      case 'overview': return <Suspense fallback={<PageState/>}><OverviewPage/></Suspense>
      case 'task': return <TaskSettingsPage/>
      case 'output': return <OutputSettingsPage/>
      case 'advanced': return <AdvancedSettingsPage/>
      case 'appearance': return <AppearancePage openConnection={() => setConnectionOpen(true)}/>
      case 'logs': return <LogsPage/>
      case 'about': return <AboutPage/>
      default: return <PlaceholderPage entry={item}/>
    }
  }
  return <><ThemeController/><a href="#main-content" className="skip-link">{t('app.skip')}</a><div className={`app-shell${collapsed ? ' nav-collapsed' : ''}`}><aside className="sidebar"><div className="brand"><div className="brand-mark">A</div><div className="brand-name"><strong>AiNiee</strong><span>{t('app.workspace')}</span></div><Button variant="ghost" size="icon" className="sidebar-toggle" aria-label={t(collapsed ? 'app.expand' : 'app.collapse')} onClick={toggleSidebar}>{collapsed ? <Menu size={17}/> : <PanelLeftClose size={17}/>}</Button></div><nav className="navigation" aria-label={t('app.workspace')}>{workspaceGroups.map(group => <div className="nav-group" key={group}><h2>{t(`groups.${group}`)}</h2>{workspaces.filter(item => item.group === group).map(navItem)}</div>)}</nav><div className="nav-bottom">{workspaces.filter(item => item.group === 'bottom').map(navItem)}<div className="sidebar-foot"><span className="small-dot"/>{t('common.local')}</div></div></aside><div className="app-main"><header className="topbar"><div className="project-heading"><Folder size={17}/><span>{project?.project_name || t('app.noProject')}</span><ChevronRight size={13}/><strong>{t(`nav.${entry?.label ?? 'home'}`)}</strong></div><div className="topbar-tools"><div className="page-search"><Search size={15}/><input value={search} onChange={event => setSearch(event.target.value)} placeholder={t('app.search')} aria-label={t('app.search')} onKeyDown={event => { if (event.key === 'Enter' && searchResults[0]) navigate(searchResults[0].path) }}/>{search && <div className="search-results">{searchResults.length ? searchResults.map(item => <button key={item.id} onClick={() => navigate(item.path)}><item.icon size={15}/>{t(`nav.${item.label}`)}</button>) : <p>{t('app.noResults')}</p>}</div>}</div><button className={`connection-pill ${status}`} onClick={() => setConnectionOpen(true)} title={connectionError ? t(connectionError) : t('connection.change')} aria-label={t('connection.change')}><span className="small-dot"/><span>{t(`connection.${status}`)}</span></button><span className="topbar-separator"/><Button variant={agentOpen ? 'secondary' : 'ghost'} size="icon" className="agent-toggle" onClick={toggleAgent} aria-label={t('agent.toggle')} aria-pressed={agentOpen} title={`${t('agent.toggle')} · Ctrl+L`}><Bot size={20}/></Button></div></header>{connectionError && <div className="connection-error" role="alert"><PlugZap size={15}/><span>{t(connectionError)}</span><button onClick={() => setConnectionOpen(true)}>{t('connection.change')}</button></div>}<div className="workspace-stage"><main id="main-content" tabIndex={-1} className="main-content"><Routes>{workspaces.map(item => <Route key={item.id} path={item.path} element={renderWorkspace(item)}/>)}<Route path="*" element={<Navigate to="/" replace/>}/></Routes></main>{agentOpen && <AgentPanel/>}{logsOpen && <section className="log-drawer" aria-label={t('task.logTitle')}><Button variant="ghost" size="icon" className="drawer-close" onClick={() => setLogsOpen(false)} aria-label={t('common.close')}><X size={17}/></Button><LogContent/></section>}</div><TaskBar onOpenLogs={() => setLogsOpen(value => !value)}/></div></div><ConnectionDialog open={connectionOpen} onClose={() => setConnectionOpen(false)}/></>
}
