import { api } from './client'

export interface DataPointValue {
  type: string
  value: unknown
}

export interface DataPoint {
  reference: string
  value: DataPointValue | null
}

export interface DataPointsResponse {
  total: number
  page: number
  page_size: number
  pages: number
  items: DataPoint[]
}

export interface DeviceNode {
  ld: string
  logical_nodes: string[]
}

export const getDatapoints = (params: {
  page?: number
  page_size?: number
  search?: string
  ld?: string
  ln?: string
}) => {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.page_size) qs.set('page_size', String(params.page_size))
  if (params.search) qs.set('search', params.search)
  if (params.ld) qs.set('ld', params.ld)
  if (params.ln) qs.set('ln', params.ln)
  return api.get<DataPointsResponse>(`/datapoints?${qs}`)
}

export const getDevices = () => api.get<DeviceNode[]>('/devices')

export const writeDatapoint = (ref: string, value: unknown, value_type?: string) =>
  api.put<{ success: boolean }>(`/datapoints/${ref}`, { value, value_type })
