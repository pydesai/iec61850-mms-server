import { useEffect, useRef } from 'react'
import { useServerStore } from '../store/serverStore'

const WS_URL = (() => {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws`
})()

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const { setStatus, appendLog, setWsConnected } = useServerStore()

  useEffect(() => {
    let destroyed = false

    function connect() {
      if (destroyed) return

      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setWsConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          switch (msg.type) {
            case 'server_status':
              setStatus(msg.data)
              break
            case 'log_entry':
              appendLog(msg.data)
              break
            case 'ping':
              ws.send(JSON.stringify({ type: 'pong' }))
              break
          }
        } catch {
          // ignore malformed messages
        }
      }

      ws.onclose = () => {
        setWsConnected(false)
        if (!destroyed) {
          reconnectRef.current = setTimeout(connect, 3000)
        }
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    return () => {
      destroyed = true
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
      wsRef.current?.close()
      setWsConnected(false)
    }
  }, [])
}
