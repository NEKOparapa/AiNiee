import { ArrowUpRight } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useVersion } from '@/api/system'

export function AboutPage() {
  const { t } = useTranslation()
  const { data } = useVersion()
  return <div className="workspace"><div className="about-card"><div className="brand-mark large">A</div><h1>{t('about.title')}</h1><p>{t('about.subtitle')}</p><span className="subtle-badge">{data?.version ?? 'AiNiee'}</span><p className="about-description">{t('about.description')}</p><a className="text-link" href="https://github.com/NEKOparapa/AiNiee" target="_blank" rel="noreferrer">{t('about.source')}<ArrowUpRight size={16}/></a><p className="workspace-tip">{t('about.note')}</p></div></div>
}
