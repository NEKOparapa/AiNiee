import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function SettingCard({ title, description, children, className }: { title: string; description: string; children: ReactNode; className?: string }) {
  return <div className={cn('setting-card', className)}><div className="setting-copy"><h3>{title}</h3><p>{description}</p></div><div className="setting-control">{children}</div></div>
}
