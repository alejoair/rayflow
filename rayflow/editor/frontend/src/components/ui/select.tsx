import * as React from "react"
import * as SelectPrimitive from "@radix-ui/react-select"
import { Check, ChevronDown } from "lucide-react"

const Select = SelectPrimitive.Root
const SelectGroup = SelectPrimitive.Group
const SelectValue = SelectPrimitive.Value

const SelectTrigger = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ children, style, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      height: 32,
      width: '100%',
      borderRadius: 6,
      border: '1px solid var(--border)',
      background: 'var(--secondary)',
      color: 'var(--foreground)',
      padding: '0 10px',
      fontSize: 13,
      cursor: 'pointer',
      outline: 'none',
      boxSizing: 'border-box',
      gap: 6,
      ...style,
    }}
    {...props}
  >
    {children}
    <SelectPrimitive.Icon asChild>
      <ChevronDown style={{ width: 14, height: 14, opacity: 0.6, flexShrink: 0 }} />
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
))
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName

const SelectContent = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ children, position = "popper", ...props }, ref) => (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={ref}
      position={position}
      style={{
        zIndex: 9999,
        minWidth: 120,
        maxHeight: 320,
        overflowY: 'auto',
        borderRadius: 8,
        border: '1px solid var(--border)',
        background: 'var(--card)',
        color: 'var(--foreground)',
        boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        padding: 4,
      }}
      {...props}
    >
      <SelectPrimitive.Viewport>{children}</SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
))
SelectContent.displayName = SelectPrimitive.Content.displayName

const SelectItem = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ children, style, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '6px 10px 6px 28px',
      fontSize: 13,
      borderRadius: 5,
      cursor: 'pointer',
      outline: 'none',
      position: 'relative',
      color: 'var(--foreground)',
      ...style,
    }}
    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'var(--secondary)' }}
    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
    {...props}
  >
    <span style={{ position: 'absolute', left: 8, display: 'flex', alignItems: 'center' }}>
      <SelectPrimitive.ItemIndicator>
        <Check style={{ width: 13, height: 13, color: 'var(--primary)' }} />
      </SelectPrimitive.ItemIndicator>
    </span>
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
))
SelectItem.displayName = SelectPrimitive.Item.displayName

const SelectLabel = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Label>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Label>
>(({ style, ...props }, ref) => (
  <SelectPrimitive.Label
    ref={ref}
    style={{ padding: '6px 10px', fontSize: 11, fontWeight: 600, color: 'var(--muted-foreground)', ...style }}
    {...props}
  />
))
SelectLabel.displayName = SelectPrimitive.Label.displayName

const SelectSeparator = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Separator>
>(({ style, ...props }, ref) => (
  <SelectPrimitive.Separator
    ref={ref}
    style={{ height: 1, background: 'var(--border)', margin: '4px -4px', ...style }}
    {...props}
  />
))
SelectSeparator.displayName = SelectPrimitive.Separator.displayName

export {
  Select, SelectGroup, SelectValue,
  SelectTrigger, SelectContent, SelectItem,
  SelectLabel, SelectSeparator,
}
