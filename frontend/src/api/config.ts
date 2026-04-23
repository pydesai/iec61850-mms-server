import { api } from './client'

export interface ServerConfig {
  port: number
  interface: string
  auth_mode: 'none' | 'password' | 'tls'
  auth_username: string | null
  auth_password: string | null
  tls_cert_path: string | null
  tls_key_path: string | null
  max_connections: number
  report_buffer_size: number
}

export interface ConfigUpdate {
  port?: number
  interface?: string
  auth_mode?: 'none' | 'password' | 'tls'
  auth_username?: string
  auth_password?: string
  max_connections?: number
}

export const getConfig = () => api.get<ServerConfig>('/config')
export const updateConfig = (data: ConfigUpdate) => api.put<{ success: boolean; config: ServerConfig }>('/config', data)
