import { useEffect, useState } from 'react'
import { ChevronDown, Menu } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { navigationSections, workflowNavigation, workspaces, workspaceForPath } from '@/workspaces/registry'

export function Sidebar({ collapsed, mobileOpen, onToggle, onExpand, onNavigate }: {
  collapsed: boolean; mobileOpen: boolean; onToggle: () => void; onExpand: () => void; onNavigate: () => void
}) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const entry = workspaceForPath(pathname)
  const [expanded, setExpanded] = useState<string[]>([])
  const [compactScreen, setCompactScreen] = useState(() => window.matchMedia('(max-width: 760px)').matches)
  useEffect(() => {
    const media = window.matchMedia('(max-width: 760px)')
    const update = () => setCompactScreen(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  const navigationExpanded = compactScreen ? mobileOpen : !collapsed
  useEffect(() => {
    const parent = navigationSections.flatMap(section => section.items).find(item => typeof item !== 'string' && item.children.includes(entry?.id ?? ''))
    if (parent && typeof parent !== 'string') setExpanded(previous => previous.includes(parent.id) ? previous : [...previous, parent.id])
  }, [entry?.id])
  const link = (id: string, child = false) => {
    const item = workspaces.find(workspace => workspace.id === id)!
    return <NavLink key={id} to={item.path} end title={t(`nav.${item.label}`)} onClick={onNavigate}
      className={({ isActive }) => `nav-item${child ? ' nav-child' : ''}${isActive ? ' active' : ''}`}>
      <item.icon size={18} strokeWidth={1.5}/><span className="nav-text">{t(`nav.${item.label}`)}</span>
    </NavLink>
  }
  return <aside className="sidebar">
    <div className="brand"><span className="brand-name">AiNiee</span><span className="brand-caption">{t('app.workspace')}</span></div>
    <div className="navigation-header"><Button variant="ghost" size="icon" className="sidebar-toggle" onClick={onToggle}
      aria-label={t(navigationExpanded ? 'app.collapse' : 'app.expand')} aria-expanded={navigationExpanded}><Menu size={19}/></Button></div>
    <nav className="navigation" aria-label={t('app.workspace')}>
      {navigationSections.map(section => <section className="nav-group" key={section.id}>
        <h2>{t(`groups.${section.id}`)}</h2>
        {section.items.map(item => {
          if (typeof item === 'string') {
            if (item !== 'workflow') return link(item)
            return <NavLink key={item} to={workflowNavigation.path} end onClick={onNavigate} title={t(`nav.${workflowNavigation.label}`)}
              className={`nav-item${entry?.group === 'project' || entry?.kind === 'home' ? ' active' : ''}`}>
              <workflowNavigation.icon size={18} strokeWidth={1.5}/><span className="nav-text">{t(`nav.${workflowNavigation.label}`)}</span>
            </NavLink>
          }
          const open = expanded.includes(item.id)
          const active = item.children.includes(entry?.id ?? '')
          return <div className={`nav-branch${open ? ' is-open' : ''}`} key={item.id}>
            <button className={`nav-item nav-branch-toggle${active ? ' branch-active' : ''}`} title={t(`nav.${item.label}`)}
              aria-expanded={open} aria-controls={`nav-${item.id}`} onClick={() => {
                const compact = !navigationExpanded
                if (compact) onExpand()
                setExpanded(previous => open && !compact ? previous.filter(id => id !== item.id) : [...new Set([...previous, item.id])])
              }}>
              <item.icon size={18} strokeWidth={1.5}/><span className="nav-text">{t(`nav.${item.label}`)}</span><ChevronDown size={14} className="nav-chevron"/>
            </button>
            <div id={`nav-${item.id}`} className="nav-children" hidden={!open}>{item.children.map(id => link(id, true))}</div>
          </div>
        })}
      </section>)}
    </nav>
    <div className="nav-bottom">{workspaces.filter(item => item.group === 'bottom').map(item => link(item.id))}
      <div className="sidebar-foot"><span className="small-dot"/>{t('common.local')}</div>
    </div>
  </aside>
}
