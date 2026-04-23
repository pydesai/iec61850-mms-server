import { useState } from 'react'
import {
  Card, Form, InputNumber, Select, Button, Radio, Input,
  Typography, Space, Alert, Divider, Upload, message, Slider, Row, Col,
} from 'antd'
import { UploadOutlined, SaveOutlined, ReloadOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getConfig, updateConfig } from '../api/config'
import { getInterfaces } from '../api/server'
import type { ConfigUpdate } from '../api/config'

const { Title, Text, Paragraph } = Typography

export default function Settings() {
  const [form] = Form.useForm()
  const [authMode, setAuthMode] = useState<'none' | 'password' | 'tls'>('none')
  const [tlsUploading, setTlsUploading] = useState(false)
  const qc = useQueryClient()

  const configQuery = useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
  })

  // Populate form when config loads
  if (configQuery.data && !configQuery.isFetching) {
    form.setFieldsValue(configQuery.data)
  }

  const interfacesQuery = useQuery({
    queryKey: ['interfaces'],
    queryFn: getInterfaces,
  })

  const saveMut = useMutation({
    mutationFn: (data: ConfigUpdate) => updateConfig(data),
    onSuccess: () => {
      message.success('Configuration saved — server restarted with new settings')
      qc.invalidateQueries({ queryKey: ['config'] })
      qc.invalidateQueries({ queryKey: ['server-status'] })
    },
    onError: (err: Error) => {
      message.error(`Save failed: ${err.message}`)
    },
  })

  const onFinish = (values: ConfigUpdate & { auth_mode: 'none' | 'password' | 'tls' }) => {
    saveMut.mutate(values)
  }

  const handleTlsUpload = async (certFile: File, keyFile: File) => {
    setTlsUploading(true)
    const form = new FormData()
    form.append('cert', certFile)
    form.append('key', keyFile)
    try {
      const res = await fetch('/api/config/tls/upload', { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      message.success('TLS certificates uploaded')
    } catch (err: unknown) {
      message.error(`TLS upload failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setTlsUploading(false)
    }
  }

  const interfaceOptions = [
    { value: '0.0.0.0', label: '0.0.0.0 — All Interfaces' },
    ...(interfacesQuery.data ?? [])
      .filter(i => i.address !== '0.0.0.0')
      .map(i => ({ value: i.address, label: `${i.name} — ${i.address}` })),
  ]

  return (
    <div className="page-container">
      <Title level={4} style={{ marginTop: 0, marginBottom: 20 }}>Server Settings</Title>

      <Alert
        type="info"
        showIcon
        message="Saving settings will restart the MMS server automatically."
        style={{ marginBottom: 20 }}
      />

      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        initialValues={{ port: 102, interface: '0.0.0.0', auth_mode: 'none', max_connections: 50 }}
      >
        <Row gutter={24}>
          <Col xs={24} lg={12}>
            <Card title="Network" style={{ marginBottom: 16 }}>
              <Form.Item
                label="Network Interface"
                name="interface"
                help="Select which interface the MMS server binds to"
              >
                <Select
                  options={interfaceOptions}
                  loading={interfacesQuery.isLoading}
                  placeholder="Select interface"
                />
              </Form.Item>

              <Form.Item
                label="MMS Port"
                name="port"
                rules={[{ required: true, message: 'Port is required' }]}
                help="Default: 102 (requires root/NET_BIND_SERVICE capability)"
              >
                <InputNumber min={1} max={65535} style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item label="Max Connections" name="max_connections">
                <Slider min={1} max={200} marks={{ 1: '1', 50: '50', 200: '200' }} />
              </Form.Item>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card title="Authentication" style={{ marginBottom: 16 }}>
              <Form.Item label="Authentication Mode" name="auth_mode">
                <Radio.Group onChange={(e) => setAuthMode(e.target.value)}>
                  <Space direction="vertical">
                    <Radio value="none">
                      <strong>No Authentication</strong>
                      <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>
                        Open access — any MMS client can connect
                      </Text>
                    </Radio>
                    <Radio value="password">
                      <strong>Password (ACSE)</strong>
                      <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>
                        MMS application-layer password authentication
                      </Text>
                    </Radio>
                    <Radio value="tls">
                      <strong>TLS</strong>
                      <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>
                        Transport-layer TLS encryption (IEC 62351-4)
                      </Text>
                    </Radio>
                  </Space>
                </Radio.Group>
              </Form.Item>

              {authMode === 'password' && (
                <>
                  <Form.Item label="Username" name="auth_username">
                    <Input placeholder="Username (optional)" />
                  </Form.Item>
                  <Form.Item label="Password" name="auth_password">
                    <Input.Password placeholder="Password" />
                  </Form.Item>
                </>
              )}

              {authMode === 'tls' && (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Text style={{ fontSize: 12 }}>Upload PEM certificate and private key:</Text>

                  <div style={{ display: 'flex', gap: 8 }}>
                    <Upload
                      accept=".pem,.crt,.cer"
                      showUploadList={false}
                      beforeUpload={() => false}
                      maxCount={1}
                    >
                      <Button icon={<UploadOutlined />} size="small">
                        Certificate (.pem/.crt)
                      </Button>
                    </Upload>
                    <Upload
                      accept=".pem,.key"
                      showUploadList={false}
                      beforeUpload={() => false}
                      maxCount={1}
                    >
                      <Button icon={<UploadOutlined />} size="small">
                        Private Key (.pem/.key)
                      </Button>
                    </Upload>
                  </div>

                  <Alert
                    type="warning"
                    showIcon
                    message="TLS terminates at the nginx proxy layer. Full MMS-layer TLS per IEC 62351-4 requires a custom libIEC61850 build with mbedTLS."
                    style={{ fontSize: 11 }}
                  />
                </Space>
              )}
            </Card>
          </Col>
        </Row>

        <Form.Item>
          <Space>
            <Button
              type="primary"
              htmlType="submit"
              icon={<SaveOutlined />}
              loading={saveMut.isPending}
            >
              Save & Restart Server
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                qc.invalidateQueries({ queryKey: ['config'] })
                form.resetFields()
              }}
            >
              Reset
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  )
}
