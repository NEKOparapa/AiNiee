import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { WorkspaceEntry } from './registry'
import { PageHeading } from '@/components/common/PageHeading'

export function PlaceholderPage({ entry }: { entry: WorkspaceEntry }) {
  const { t } = useTranslation()
  const Icon = entry.icon
  return <div className="workspace"><PageHeading title={t(`nav.${entry.label}`)} subtitle={t('common.unavailable')}/><div className="placeholder-state"><span className="empty-symbol"><Icon size={30} strokeWidth={1.4}/></span><h2>{t('placeholder.title')}</h2><p>{t('placeholder.detail')}</p><Link className="text-link" to="/settings/task">{t('placeholder.action')}<ArrowRight size={16}/></Link></div></div>
}
