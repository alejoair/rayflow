import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cn } from "@/lib/utils"

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link'
  size?: 'default' | 'sm' | 'lg' | 'icon'
  asChild?: boolean
}

const BASE: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  whiteSpace: 'nowrap',
  borderRadius: 6,
  fontWeight: 500,
  cursor: 'pointer',
  border: 'none',
  transition: 'opacity 0.15s, background 0.15s',
  outline: 'none',
}

const VARIANT_STYLE: Record<NonNullable<ButtonProps['variant']>, React.CSSProperties> = {
  default:     { background: 'var(--primary)',     color: '#fff' },
  destructive: { background: 'var(--destructive)', color: '#fff' },
  outline:     { background: 'var(--secondary)',   color: 'var(--foreground)', border: '1px solid var(--border)' },
  secondary:   { background: 'var(--secondary)',   color: 'var(--foreground)' },
  ghost:       { background: 'transparent',        color: 'var(--foreground)' },
  link:        { background: 'transparent',        color: 'var(--primary)', textDecoration: 'underline' },
}

const SIZE_STYLE: Record<NonNullable<ButtonProps['size']>, React.CSSProperties> = {
  default: { height: 36, padding: '0 16px', fontSize: 14 },
  sm:      { height: 32, padding: '0 12px', fontSize: 13 },
  lg:      { height: 44, padding: '0 24px', fontSize: 15 },
  icon:    { height: 36, width: 36,         fontSize: 14 },
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', asChild = false, style, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        ref={ref}
        className={cn(className)}
        style={{ ...BASE, ...VARIANT_STYLE[variant], ...SIZE_STYLE[size], ...style }}
        onMouseEnter={e => { if (!props.disabled) (e.currentTarget as HTMLElement).style.opacity = '0.85' }}
        onMouseLeave={e => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button }
