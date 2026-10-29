import { useEffect, useRef, useState } from 'react'
import { PlugZap, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ConnectionError, useConnectionStore } from '@/stores/connection'

export function ConnectionDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const dialog = useRef<HTMLDialogElement>(null)
  const connection = useConnectionStore(state => state.connection)
  const connect = useConnectionStore(state => state.connect)
  const disconnect = useConnectionStore(state => state.disconnect)
  const [api, setApi] = useState('http://127.0.0.1:8000')
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    if (open) {
      setApi(connection?.api ?? 'http://127.0.0.1:8000')
      setToken(connection?.token ?? '')
      setError('')
      dialog.current?.showModal()
    } else dialog.current?.close()
  }, [open, connection])
  return <dialog ref={dialog} className="connection-dialog" onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose() }}><div className="dialog-heading"><span className="card-symbol"><PlugZap size={22}/></span><Button variant="ghost" size="icon" onClick={onClose} aria-label={t('common.close')}><X size={18}/></Button></div><h2>{t('connection.title')}</h2><p>{t('connection.description')}</p><form onSubmit={event => { event.preventDefault(); try { connect(api.trim(), token.trim()); onClose() } catch (reason) { setError(reason instanceof ConnectionError ? reason.code : 'connection.requestFailed') } }}><label htmlFor="service-address">{t('connection.address')}</label><Input id="service-address" value={api} onChange={event => setApi(event.target.value)} autoComplete="off" spellCheck={false}/><label htmlFor="service-token">{t('connection.token')}</label><Input id="service-token" type="password" value={token} onChange={event => setToken(event.target.value)} autoComplete="off" placeholder={t('connection.tokenPlaceholder')}/>{error && <p className="form-error" role="alert">{t(error)}</p>}<div className="dialog-actions">{connection && <Button type="button" variant="outline" onClick={() => { disconnect(); onClose() }}>{t('connection.disconnect')}</Button>}<Button type="submit">{t('connection.connect')}</Button></div></form></dialog>
}
