import * as React from "react"

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ type, style, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      style={{
        display: 'flex',
        width: '100%',
        height: 32,
        borderRadius: 6,
        border: '1px solid var(--border)',
        background: 'var(--secondary)',
        color: 'var(--foreground)',
        padding: '0 10px',
        fontSize: 13,
        outline: 'none',
        boxSizing: 'border-box',
        ...style,
      }}
      {...props}
    />
  )
)
Input.displayName = "Input"

export { Input }
