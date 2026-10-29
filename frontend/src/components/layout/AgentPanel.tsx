import { ArrowUp, Bot, Sparkles, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useLayoutStore } from '@/stores/layout'

export function AgentPanel() {
  const { t } = useTranslation()
  const setOpen = useLayoutStore(state => state.setAgentPanelOpen)
  return <aside className="agent-panel" aria-label={t('agent.title')}><header><div><Bot size={18}/><h2>{t('agent.title')}</h2></div><Button variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label={t('agent.close')}><X size={16}/></Button></header><div className="agent-content"><div className="agent-orbit" aria-hidden="true"><Sparkles size={30} strokeWidth={1.3}/><span/></div><span className="subtle-badge">{t('agent.badge')}</span><h3>{t('agent.headline')}</h3><p>{t('agent.detail')}</p></div><div className="agent-bottom"><div className="agent-input"><textarea disabled placeholder={t('agent.input')} aria-label={t('agent.input')}/><button disabled aria-label={t('agent.input')}><ArrowUp size={17}/></button></div><p><span>{t('agent.shortcut')}</span><kbd>Ctrl L</kbd></p></div></aside>
}
