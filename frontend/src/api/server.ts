import { api } from './client'
import type { ServerStatus } from '../store/serverStore'

export interface NetworkInterface {
  name: string
  address: string
  family: string
  netmask: string | null
}

export const getServerStatus = () => api.get<ServerStatus>('/server/status')
export const startServer = () => api.post<{ success: boolean; status: ServerStatus }>('/server/start')
export const stopServer = () => api.post<{ success: boolean }>('/server/stop')
export const getInterfaces = () => api.get<NetworkInterface[]>('/server/interfaces')
