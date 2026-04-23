import { useState } from 'react'
import { Upload, Button, message, Alert } from 'antd'
import { UploadOutlined, FileOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { useQueryClient } from '@tanstack/react-query'

interface UploadResult {
  filename: string
  size_bytes: number
  ied_count: number
  device_count: number
  ln_count: number
}

export default function SCLUploader() {
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const qc = useQueryClient()

  const handleUpload = async (file: File) => {
    setUploading(true)
    setError(null)
    setResult(null)

    const form = new FormData()
    form.append('file', file)

    try {
      const res = await fetch('/api/scl/upload', { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Upload failed')
      setResult(data)
      message.success(`Uploaded ${data.filename}`)
      qc.invalidateQueries({ queryKey: ['scl-files'] })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setError(msg)
      message.error(msg)
    } finally {
      setUploading(false)
    }
    return false // prevent default upload
  }

  const handleLoad = async () => {
    if (!result) return
    setLoading(true)
    try {
      const res = await fetch(`/api/scl/load/${encodeURIComponent(result.filename)}`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Load failed')
      message.success(`Model loaded: ${data.da_count} data attributes`)
      qc.invalidateQueries({ queryKey: ['server-status'] })
      qc.invalidateQueries({ queryKey: ['devices'] })
      qc.invalidateQueries({ queryKey: ['datapoints'] })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Load failed'
      message.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Upload
        accept=".icd,.cid,.scd,.iid"
        showUploadList={false}
        beforeUpload={(file) => { handleUpload(file); return false }}
      >
        <Button icon={<UploadOutlined />} loading={uploading} block>
          Upload SCL File (.icd / .cid / .scd)
        </Button>
      </Upload>

      {error && <Alert type="error" message={error} showIcon />}

      {result && (
        <div style={{ background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6, padding: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <FileOutlined style={{ color: '#52c41a' }} />
            <strong>{result.filename}</strong>
          </div>
          <div style={{ fontSize: 12, color: '#666', lineHeight: 1.8 }}>
            <div>IEDs: <strong>{result.ied_count}</strong></div>
            <div>Logical Devices: <strong>{result.device_count}</strong></div>
            <div>Logical Nodes: <strong>{result.ln_count}</strong></div>
          </div>
          <Button
            type="primary"
            size="small"
            style={{ marginTop: 8 }}
            loading={loading}
            onClick={handleLoad}
          >
            Load into Server
          </Button>
        </div>
      )}
    </div>
  )
}
