import { ArrowUpRight, FileOutput, FolderOpen, Settings2, SlidersHorizontal } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

export function HomePage() {
  const { t } = useTranslation()
  const cards = [ ['task', '/settings/task', SlidersHorizontal], ['output', '/settings/output', FileOutput], ['advanced', '/settings/advanced', Settings2] ] as const
  return <div className="workspace home-page"><div className="welcome"><span className="eyebrow">{t('home.eyebrow')}</span><h1>{t('home.title')}</h1><p>{t('home.intro')}</p><div className="welcome-mark" aria-hidden="true"><span>文</span><span>A</span></div></div><section className="section-heading"><h2>{t('home.setup')}</h2><p>{t('home.setupDetail')}</p></section><div className="start-cards">{cards.map(([key, path, Icon]) => <Link to={path} className="start-card" key={key}><span className="card-symbol"><Icon size={22} /></span><ArrowUpRight size={17} className="card-arrow" /><h3>{t(`home.${key}`)}</h3><p>{t(`home.${key}Detail`)}</p><span className="card-link">{t('home.settingsLink')} <span aria-hidden="true">→</span></span></Link>)}</div><div className="project-empty"><FolderOpen size={35} strokeWidth={1.3}/><div><h2>{t('home.projects')}</h2><p>{t('home.projectsDetail')}</p></div><span className="subtle-badge">{t('common.unavailable')}</span></div><p className="workspace-tip">{t('home.tip')}</p></div>
}
