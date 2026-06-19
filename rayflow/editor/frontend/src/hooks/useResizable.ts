import { useCallback, useEffect, useRef, useState } from 'react'

interface Options {
  key: string
  default: number
  min: number
  max: number
  /** 'left'/'right' para sidebars horizontales; 'top' para panels que crecen hacia arriba */
  side: 'left' | 'right' | 'top'
}

export function useResizable({ key, default: def, min, max, side }: Options) {
  const stored = localStorage.getItem(key)
  const [size, setSize] = useState<number>(stored ? Number(stored) : def)
  const dragging = useRef(false)
  const startPos = useRef(0)
  const startSize = useRef(0)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = true
    startPos.current = side === 'top' ? e.clientY : e.clientX
    startSize.current = size
    document.body.style.cursor = side === 'top' ? 'row-resize' : 'col-resize'
    document.body.style.userSelect = 'none'
  }, [size, side])

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return
      let delta: number
      if (side === 'top') {
        delta = startPos.current - e.clientY   // arrastrar arriba = agrandar
      } else if (side === 'right') {
        delta = startPos.current - e.clientX   // arrastrar izq = agrandar
      } else {
        delta = e.clientX - startPos.current   // arrastrar der = agrandar
      }
      const next = Math.min(max, Math.max(min, startSize.current + delta))
      setSize(next)
    }
    const onUp = () => {
      if (!dragging.current) return
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      setSize(w => { localStorage.setItem(key, String(w)); return w })
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [key, min, max, side])

  const isVertical = side === 'top'

  const handleStyle: React.CSSProperties = isVertical
    ? {
        position: 'absolute',
        left: 0,
        right: 0,
        height: 4,
        top: 0,
        cursor: 'row-resize',
        zIndex: 20,
      }
    : {
        position: 'absolute',
        top: 0,
        bottom: 0,
        width: 4,
        cursor: 'col-resize',
        zIndex: 20,
        ...(side === 'right' ? { left: 0 } : { right: 0 }),
      }

  return { width: size, height: size, size, onMouseDown, handleStyle }
}
