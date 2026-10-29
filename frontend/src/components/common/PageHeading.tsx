import type { ReactNode } from 'react'

export function PageHeading({ title, subtitle, children }: { title: string; subtitle: string; children?: ReactNode }) {
  return <header className="page-heading"><div><h1>{title}</h1><p>{subtitle}</p></div>{children}</header>
}
