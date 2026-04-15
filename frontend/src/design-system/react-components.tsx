import React from 'react'

type ButtonVariant = 'primary' | 'ghost' | 'text'

export function DsButton({ children, variant = 'primary' }: { children: React.ReactNode; variant?: ButtonVariant }) {
  return <button className={`ds-btn ds-btn--${variant}`}>{children}</button>
}

export function DsCard({
  title,
  description,
  children
}: {
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <section className="ds-card">
      <header className="ds-card__header">
        <h3>{title}</h3>
        {description ? <p>{description}</p> : null}
      </header>
      <div>{children}</div>
    </section>
  )
}

export function DsList({
  items
}: {
  items: Array<{ id: string; label: string; meta?: string; value: string }>
}) {
  return (
    <ul className="ds-list">
      {items.map((item) => (
        <li key={item.id} className="ds-list__item">
          <div>
            <strong>{item.label}</strong>
            {item.meta ? <p>{item.meta}</p> : null}
          </div>
          <span>{item.value}</span>
        </li>
      ))}
    </ul>
  )
}

export function DsNavBar({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <nav className="ds-nav">
      <div>
        <h2>{title}</h2>
        <p>Unified Design Language</p>
      </div>
      <div>{right}</div>
    </nav>
  )
}
