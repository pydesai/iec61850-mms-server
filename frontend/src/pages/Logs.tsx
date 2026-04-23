import { useEffect, useRef, useState, useCallback } from 'react'
import { Space, Button, Select, Typography, Badge, Tooltip } from 'antd'
import { ClearOutlined, DownloadOutlined, PauseOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import { useServerStore } from '../store/serverStore'
import type { LogEntry } from '../store/serverStore'

const { Title, Text } = Typography

const LEVEL_COLORS: Record<string, string> = {
  ERROR: '\x1b[1;31m',  // bold red
  WARN:  '\x1b[1;33m',  // bold yellow
  INFO:  '\x1b[1;36m',  // bold cyan
  DEBUG: '\x1b[0;37m',  // gray
}
const RESET = '\x1b[0m'
const DIM   = '\x1b[2m'

function formatLogLine(entry: LogEntry): string {
  const ts = entry.timestamp.slice(11, 23)  // HH:MM:SS.mmm
  const color = LEVEL_COLORS[entry.level] ?? '\x1b[0m'
  const padded = entry.level.padEnd(5)
  const hex = entry.raw_hex ? `\r\n${DIM}  hex: ${entry.raw_hex}${RESET}` : ''
  return `${DIM}${ts}${RESET} ${color}${padded}${RESET} ${entry.message}${hex}\r\n`
}

export default function Logs() {
  const termRef = useRef<HTMLDivElement>(null)
  const xtermRef = useRef<Terminal | null>(null)
  const fitRef = useRef<FitAddon | null>(null)
  const pausedRef = useRef(false)
  const [paused, setPaused] = useState(false)
  const [levelFilter, setLevelFilter] = useState<string>('ALL')
  const { logs, clearLogs } = useServerStore()
  const writtenCount = useRef(0)

  useEffect(() => {
    if (!termRef.current) return

    const term = new Terminal({
      theme: {
        background: '#0d1117',
        foreground: '#c9d1d9',
        cursor: '#58a6ff',
        selectionBackground: 'rgba(56, 139, 253, 0.3)',
      },
      fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',
      fontSize: 12,
      lineHeight: 1.4,
      scrollback: 5000,
      cursorBlink: false,
      convertEol: true,
    })

    const fitAddon = new FitAddon()
    const linksAddon = new WebLinksAddon()
    term.loadAddon(fitAddon)
    term.loadAddon(linksAddon)
    term.open(termRef.current)
    fitAddon.fit()

    xtermRef.current = term
    fitRef.current = fitAddon

    term.writeln('\x1b[1;36mIEC 61850 MMS Simulator — Log Viewer\x1b[0m')
    term.writeln('\x1b[2m─────────────────────────────────────\x1b[0m')
    term.writeln('')

    const observer = new ResizeObserver(() => fitAddon.fit())
    observer.observe(termRef.current)

    return () => {
      observer.disconnect()
      term.dispose()
    }
  }, [])

  // Write new log entries to terminal
  useEffect(() => {
    const term = xtermRef.current
    if (!term) return
    if (pausedRef.current) return

    const newEntries = logs.slice(writtenCount.current)
    for (const entry of newEntries) {
      if (levelFilter !== 'ALL' && entry.level !== levelFilter) continue
      term.write(formatLogLine(entry))
    }
    writtenCount.current = logs.length
  }, [logs, levelFilter])

  const handleClear = useCallback(() => {
    clearLogs()
    xtermRef.current?.clear()
    writtenCount.current = 0
  }, [clearLogs])

  const handlePauseToggle = useCallback(() => {
    pausedRef.current = !pausedRef.current
    setPaused(pausedRef.current)
  }, [])

  const handleDownload = useCallback(() => {
    const filtered = levelFilter === 'ALL'
      ? logs
      : logs.filter(e => e.level === levelFilter)

    const text = filtered
      .map(e => `${e.timestamp} ${e.level.padEnd(5)} ${e.message}${e.raw_hex ? `\n  hex: ${e.raw_hex}` : ''}`)
      .join('\n')

    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `iecmms-logs-${new Date().toISOString().slice(0, 19)}.log`
    a.click()
    URL.revokeObjectURL(url)
  }, [logs, levelFilter])

  const levelCounts = {
    ERROR: logs.filter(e => e.level === 'ERROR').length,
    WARN:  logs.filter(e => e.level === 'WARN').length,
    INFO:  logs.filter(e => e.level === 'INFO').length,
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', padding: 16, gap: 12 }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <Space align="center">
          <Title level={4} style={{ margin: 0 }}>Logs</Title>
          <Badge count={levelCounts.ERROR} style={{ backgroundColor: '#ff4d4f' }} />
          <Text type="secondary" style={{ fontSize: 12 }}>{logs.length} entries</Text>
        </Space>

        <Space>
          <Select
            value={levelFilter}
            onChange={(v) => { setLevelFilter(v); writtenCount.current = 0; xtermRef.current?.clear() }}
            style={{ width: 120 }}
            options={[
              { value: 'ALL',   label: 'All Levels' },
              { value: 'ERROR', label: '🔴 ERROR' },
              { value: 'WARN',  label: '🟡 WARN' },
              { value: 'INFO',  label: '🔵 INFO' },
              { value: 'DEBUG', label: '⚪ DEBUG' },
            ]}
          />

          <Tooltip title={paused ? 'Resume' : 'Pause'}>
            <Button
              icon={paused ? <PlayCircleOutlined /> : <PauseOutlined />}
              onClick={handlePauseToggle}
              type={paused ? 'primary' : 'default'}
            >
              {paused ? 'Resume' : 'Pause'}
            </Button>
          </Tooltip>

          <Tooltip title="Download logs">
            <Button icon={<DownloadOutlined />} onClick={handleDownload} />
          </Tooltip>

          <Tooltip title="Clear logs">
            <Button icon={<ClearOutlined />} onClick={handleClear} danger />
          </Tooltip>
        </Space>
      </div>

      {/* Level summary chips */}
      <Space style={{ flexShrink: 0 }}>
        <Badge color="#ff4d4f" text={`${levelCounts.ERROR} errors`} />
        <Badge color="#faad14" text={`${levelCounts.WARN} warnings`} />
        <Badge color="#1677ff" text={`${levelCounts.INFO} info`} />
        {paused && <Badge color="orange" text="PAUSED" />}
      </Space>

      {/* xterm.js terminal */}
      <div
        ref={termRef}
        style={{
          flex: 1,
          background: '#0d1117',
          borderRadius: 8,
          overflow: 'hidden',
          border: '1px solid #30363d',
        }}
      />
    </div>
  )
}
