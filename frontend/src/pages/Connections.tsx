import { Table, Card, Statistic, Row, Col, Badge, Typography, Empty } from 'antd'
import { ApiOutlined } from '@ant-design/icons'
import { useServerStore } from '../store/serverStore'

const { Title, Text } = Typography

export default function Connections() {
  const { status } = useServerStore()
  const count = status.connections

  const rows = Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    label: `MMS Client ${i + 1}`,
    protocol: 'ISO/IEC 8802-3 → MMS',
    port: status.port,
  }))

  const columns = [
    {
      title: '#',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: 'Client',
      dataIndex: 'label',
      key: 'label',
      render: (label: string) => (
        <Badge status="processing" text={label} />
      ),
    },
    {
      title: 'Protocol',
      dataIndex: 'protocol',
      key: 'protocol',
      render: (p: string) => <Text type="secondary" style={{ fontSize: 12 }}>{p}</Text>,
    },
    {
      title: 'Server Port',
      dataIndex: 'port',
      key: 'port',
      width: 120,
      render: (p: number) => <Text code>{p}</Text>,
    },
  ]

  return (
    <div className="page-container">
      <Title level={4} style={{ marginTop: 0, marginBottom: 20 }}>Active Connections</Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="Connected MMS Clients"
              value={count}
              prefix={<ApiOutlined />}
              valueStyle={{ color: count > 0 ? '#52c41a' : '#d9d9d9', fontSize: 40 }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Server Status"
              value={status.running ? 'Running' : 'Stopped'}
              valueStyle={{ color: status.running ? '#52c41a' : '#ff4d4f' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Listening On"
              value={status.running ? `${status.interface}:${status.port}` : '—'}
              valueStyle={{ fontSize: 16 }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Connected Clients">
        {count === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              status.running
                ? 'No MMS clients connected — connect using any IEC 61850 MMS client to this server\'s IP on port ' + status.port
                : 'Server is not running'
            }
          />
        ) : (
          <Table
            dataSource={rows}
            columns={columns}
            rowKey="id"
            size="small"
            pagination={false}
          />
        )}

        <div style={{ marginTop: 16, padding: '12px 16px', background: '#fffbe6', borderRadius: 6, border: '1px solid #ffe58f' }}>
          <Text style={{ fontSize: 12, color: '#875500' }}>
            <strong>Note:</strong> Connection IP addresses are not available in the current build.
            Full PDU tracing (raw RX/TX bytes) requires a custom libIEC61850 build with transport callbacks.
            Connection count updates in real-time via WebSocket.
          </Text>
        </div>
      </Card>
    </div>
  )
}
