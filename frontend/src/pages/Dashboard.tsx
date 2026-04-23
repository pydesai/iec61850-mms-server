import { Row, Col, Card, Statistic, Button, Space, Tag, Alert, Typography, List } from 'antd'
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  ApiOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  NodeIndexOutlined,
} from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { startServer, stopServer } from '../api/server'
import { useServerStore } from '../store/serverStore'
import SCLUploader from '../components/SCLUploader'

const { Title, Text } = Typography

function formatUptime(seconds: number | null): string {
  if (seconds === null) return '—'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  return h > 0 ? `${h}h ${m}m ${s}s` : m > 0 ? `${m}m ${s}s` : `${s}s`
}

export default function Dashboard() {
  const { status, logs } = useServerStore()
  const qc = useQueryClient()

  const startMut = useMutation({
    mutationFn: startServer,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['server-status'] }),
  })
  const stopMut = useMutation({
    mutationFn: stopServer,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['server-status'] }),
  })

  const recentLogs = logs.slice(-8).reverse()
  const errorCount = logs.filter(l => l.level === 'ERROR').length

  return (
    <div className="page-container">
      <Title level={4} style={{ marginTop: 0, marginBottom: 20 }}>Dashboard</Title>

      <Row gutter={[16, 16]}>
        {/* Server Control Card */}
        <Col xs={24} lg={8}>
          <Card
            title="MMS Server"
            extra={
              <Tag color={status.running ? 'success' : 'error'} style={{ fontWeight: 600 }}>
                {status.running ? 'RUNNING' : 'STOPPED'}
              </Tag>
            }
            style={{ height: '100%' }}
          >
            <Space direction="vertical" style={{ width: '100%' }} size={16}>
              <Row gutter={8}>
                <Col span={12}>
                  <Statistic
                    title="Port"
                    value={status.port}
                    prefix={<NodeIndexOutlined />}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="Interface"
                    value={status.interface}
                    valueStyle={{ fontSize: 14 }}
                  />
                </Col>
              </Row>

              {status.running && (
                <Row gutter={8}>
                  <Col span={12}>
                    <Statistic
                      title="Uptime"
                      value={formatUptime(status.uptime)}
                      prefix={<ClockCircleOutlined />}
                      valueStyle={{ fontSize: 14 }}
                    />
                  </Col>
                  <Col span={12}>
                    <Statistic
                      title="Model"
                      value={status.scl_source}
                      valueStyle={{ fontSize: 13 }}
                    />
                  </Col>
                </Row>
              )}

              <Space>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={() => startMut.mutate()}
                  disabled={status.running}
                  loading={startMut.isPending}
                >
                  Start
                </Button>
                <Button
                  danger
                  icon={<PauseCircleOutlined />}
                  onClick={() => stopMut.mutate()}
                  disabled={!status.running}
                  loading={stopMut.isPending}
                >
                  Stop
                </Button>
              </Space>

              {startMut.isError && (
                <Alert
                  type="error"
                  message={(startMut.error as Error)?.message}
                  showIcon
                  style={{ marginTop: 8 }}
                />
              )}
            </Space>
          </Card>
        </Col>

        {/* Connection Count Card */}
        <Col xs={24} lg={8}>
          <Card title="Active Connections" style={{ height: '100%' }}>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <Statistic
                value={status.connections}
                prefix={<ApiOutlined />}
                valueStyle={{
                  fontSize: 64,
                  fontWeight: 700,
                  color: status.connections > 0 ? '#52c41a' : '#d9d9d9',
                }}
              />
              <Text type="secondary">MMS Clients Connected</Text>
            </div>
            <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 12, marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {status.running
                  ? `Listening on ${status.interface}:${status.port}`
                  : 'Server not running'}
              </Text>
            </div>
          </Card>
        </Col>

        {/* Data Points Card */}
        <Col xs={24} lg={8}>
          <Card title="Data Model" style={{ height: '100%' }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Statistic
                title="Data Attributes"
                value={status.da_count}
                prefix={<DatabaseOutlined />}
                valueStyle={{ color: '#1677ff' }}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                Loaded from: <strong>{status.scl_source}</strong>
              </Text>
            </Space>
          </Card>
        </Col>

        {/* SCL Upload Card */}
        <Col xs={24} lg={12}>
          <Card title="SCL Configuration">
            <SCLUploader />
          </Card>
        </Col>

        {/* Recent Log Events */}
        <Col xs={24} lg={12}>
          <Card
            title="Recent Events"
            extra={
              errorCount > 0 && (
                <Tag color="error">{errorCount} error{errorCount > 1 ? 's' : ''}</Tag>
              )
            }
          >
            <List
              size="small"
              dataSource={recentLogs}
              locale={{ emptyText: 'No log events yet' }}
              renderItem={(entry) => (
                <List.Item style={{ padding: '4px 0' }}>
                  <Space size={8}>
                    <Tag
                      color={
                        entry.level === 'ERROR' ? 'error'
                          : entry.level === 'WARN' ? 'warning'
                            : 'default'
                      }
                      style={{ fontSize: 10, margin: 0 }}
                    >
                      {entry.level}
                    </Tag>
                    <Text style={{ fontSize: 12 }} ellipsis={{ tooltip: entry.message }}>
                      {entry.message}
                    </Text>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
