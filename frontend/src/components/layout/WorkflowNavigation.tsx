import { ArrowLeft } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { workflowWorkspaces } from '@/workspaces/registry'

export function WorkflowNavigation() {
  const { t } = useTranslation()
  return <nav className="workflow-navigation" aria-label={t('app.projectWorkflow')}>
    <NavLink to="/" className="workflow-back" title={t('app.backToProjects')}><ArrowLeft size={17}/><span>{t('app.backToProjects')}</span></NavLink>
    <div className="workflow-tabs">{workflowWorkspaces.map(item => <NavLink key={item.id} to={item.path} end
      className={({ isActive }) => `workflow-tab${isActive ? ' active' : ''}`}><item.icon size={16}/>{t(`nav.${item.label}`)}</NavLink>)}</div>
  </nav>
}
