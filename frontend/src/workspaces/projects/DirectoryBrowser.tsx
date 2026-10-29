import { useEffect, useRef, useState } from 'react'
import { ArrowUp, ChevronRight, Folder, HardDrive, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useDirectoryListing } from '@/api/projects'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ProjectFeedback } from './ProjectFeedback'

export function DirectoryBrowser({ initialPath, onSelect, onClose }: { initialPath: string; onSelect: (path: string) => void; onClose: () => void }) {
  const { t } = useTranslation('projects')
  const dialog = useRef<HTMLDialogElement>(null)
  const [path, setPath] = useState(initialPath)
  const [input, setInput] = useState(initialPath)
  const listing = useDirectoryListing(path, true)
  useEffect(() => { dialog.current?.showModal(); return () => dialog.current?.close() }, [])
  useEffect(() => { if (listing.data) setInput(listing.data.path) }, [listing.data])
  const navigate = (next: string) => { setInput(next); setPath(next) }
  return <dialog ref={dialog} className="project-dialog directory-dialog" aria-labelledby="directory-title" onCancel={onClose}>
    <header><div><h2 id="directory-title">{t('directoryTitle')}</h2><p>{t('directoryDetail')}</p></div><Button variant="ghost" size="icon" aria-label={t('close')} onClick={onClose}><X size={18}/></Button></header>
    <form className="directory-path" onSubmit={event => { event.preventDefault(); navigate(input.trim()) }}>
      <label className="sr-only" htmlFor="directory-path">{t('location')}</label><Input id="directory-path" value={input} onChange={e => setInput(e.target.value)}/><Button type="submit" variant="outline">{t('go')}</Button>
    </form>
    <div className="directory-toolbar"><Button variant="ghost" size="sm" disabled={!listing.data?.parent} onClick={() => navigate(listing.data!.parent!)}><ArrowUp size={15}/>{t('parent')}</Button>
      <Button variant="ghost" size="sm" onClick={() => navigate('')}>{t('defaultDirectory')}</Button>
      {listing.data?.roots.map(root => <Button key={root} variant="ghost" size="sm" onClick={() => navigate(root)}><HardDrive size={14}/>{root}</Button>)}
    </div>
    <div className="directory-entries">
      <ProjectFeedback loading={listing.isPending} error={listing.error} retry={() => void listing.refetch()}/>
      {listing.data?.entries.filter(entry => entry.is_directory).map(entry => <button className="directory-entry" key={entry.path} onClick={() => navigate(entry.path)}><Folder size={18}/><span>{entry.name}</span><ChevronRight size={15}/></button>)}
      {listing.isSuccess && !listing.data.entries.some(entry => entry.is_directory) && <p className="directory-empty">{t('emptyDirectory')}</p>}
    </div>
    <footer><Button variant="outline" onClick={onClose}>{t('cancel')}</Button><Button disabled={!listing.data || listing.isFetching || listing.isError} onClick={() => { onSelect(listing.data!.path); onClose() }}>{t('choose')}</Button></footer>
  </dialog>
}
