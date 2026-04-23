import { create } from 'zustand'

export interface ServerStatus {
  running: boolean
  connections: number
  uptime: number | null
  port: number
  interface: string
  scl_source: string
  da_count: number
}

export interface LogEntry {
  level: 'ERROR' | 'WARN' | 'INFO' | 'DEBUG'
  message: string
  timestamp: string
  raw_hex?: string | null
}

interface ServerStore {
  status: ServerStatus
  logs: LogEntry[]
  maxLogs: number
  wsConnected: boolean
  setStatus: (s: Partial<ServerStatus>) => void
  appendLog: (entry: LogEntry) => void
  clearLogs: () => void
  setWsConnected: (v: boolean) => void
}

const defaultStatus: ServerStatus = {
  running: false,
  connections: 0,
  uptime: null,
  port: 102,
  interface: '0.0.0.0',
  scl_source: 'default',
  da_count: 0,
}

export const useServerStore = create<ServerStore>((set) => ({
  status: defaultStatus,
  logs: [],
  maxLogs: 2000,
  wsConnected: false,

  setStatus: (s) =>
    set((state) => ({ status: { ...state.status, ...s } })),

  appendLog: (entry) =>
    set((state) => ({
      logs: state.logs.length >= state.maxLogs
        ? [...state.logs.slice(1), entry]
        : [...state.logs, entry],
    })),

  clearLogs: () => set({ logs: [] }),

  setWsConnected: (v) => set({ wsConnected: v }),
}))
