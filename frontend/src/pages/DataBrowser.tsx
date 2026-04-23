import { useState, useCallback } from 'react'
import {
  Layout, Tree, Table, Input, Space, Tag, Button, Modal, Form,
  InputNumber, Switch, Typography, Tooltip, Spin, Select, Alert,
} from 'antd'
import { SearchOutlined, EditOutlined, ReloadOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getDatapoints, getDevices, writeDatapoint } from '../api/datapoints'
import type { DataPoint } from '../api/datapoints'

const { Sider, Content } = Layout
const { Text } = Typography

const LEVEL_COLORS: Record<string, string> = {
  MX: 'blue', ST: 'green', CF: 'orange', SP: 'purple',
  SV: 'cyan', CO: 'red', DC: 'geekblue',
}

function extractFC(ref: string): string {
  const m = ref.match(/\$([A-Z]{2})\$/)
  return m ? m[1] : '??'
}

function extractType(val: DataPoint['value']): string {
  return val?.type ?? 'UNKNOWN'
}

function formatValue(val: DataPoint['value']): string {
  if (!val) return '—'
  if (val.value === null || val.value === undefined) return '—'
  if (typeof val.value === 'number') return String(Number(val.value.toFixed(4)))
  return String(val.value)
}

interface WriteModalState {
  open: boolean
  ref: string
  currentValue: DataPoint['value']
}

export default function DataBrowser() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [search, setSearch] = useState('')
  const [selectedLD, setSelectedLD] = useState<string>('')
  const [selectedLN, setSelectedLN] = useState<string>('')
  const [writeModal, setWriteModal] = useState<WriteModalState>({ open: false, ref: '', currentValue: null })
  const [writeValue, setWriteValue] = useState<string>('')
  const qc = useQueryClient()

  const devicesQuery = useQuery({
    queryKey: ['devices'],
    queryFn: getDevices,
    staleTime: 30_000,
  })

  const dpQuery = useQuery({
    queryKey: ['datapoints', page, pageSize, search, selectedLD, selectedLN],
    queryFn: () => getDatapoints({ page, page_size: pageSize, search, ld: selectedLD, ln: selectedLN }),
    refetchInterval: 5000,
  })

  const writeMut = useMutation({
    mutationFn: ({ ref, value }: { ref: string; value: string }) => {
      const currentType = writeModal.currentValue?.type
      let parsed: unknown = value
      if (currentType === 'FLOAT32') parsed = parseFloat(value)
      else if (currentType === 'INT32' || currentType === 'UINT32') parsed = parseInt(value, 10)
      else if (currentType === 'BOOLEAN') parsed = value === 'true'
      return writeDatapoint(ref, parsed)
    },
    onSuccess: () => {
      setWriteModal({ open: false, ref: '', currentValue: null })
      qc.invalidateQueries({ queryKey: ['datapoints'] })
    },
  })

  const treeData = (devicesQuery.data ?? []).map((dev) => ({
    key: dev.ld,
    title: dev.ld,
    children: dev.logical_nodes.map((ln) => ({
      key: `${dev.ld}/${ln}`,
      title: ln,
    })),
  }))

  const onTreeSelect = useCallback((keys: React.Key[]) => {
    const key = keys[0] as string ?? ''
    if (key.includes('/')) {
      const [ld, ln] = key.split('/')
      setSelectedLD(ld)
      setSelectedLN(ln)
    } else {
      setSelectedLD(key)
      setSelectedLN('')
    }
    setPage(1)
  }, [])

  const columns = [
    {
      title: 'Reference',
      dataIndex: 'reference',
      key: 'reference',
      ellipsis: true,
      render: (ref: string) => (
        <Tooltip title={ref}>
          <Text code style={{ fontSize: 11 }}>{ref}</Text>
        </Tooltip>
      ),
    },
    {
      title: 'FC',
      key: 'fc',
      width: 60,
      render: (_: unknown, row: DataPoint) => {
        const fc = extractFC(row.reference)
        return <Tag color={LEVEL_COLORS[fc] ?? 'default'} style={{ fontSize: 10 }}>{fc}</Tag>
      },
    },
    {
      title: 'Type',
      key: 'type',
      width: 90,
      render: (_: unknown, row: DataPoint) => (
        <Tag style={{ fontSize: 10 }}>{extractType(row.value)}</Tag>
      ),
    },
    {
      title: 'Value',
      key: 'value',
      width: 140,
      render: (_: unknown, row: DataPoint) => (
        <Text style={{ fontSize: 12, fontFamily: 'monospace' }}>
          {formatValue(row.value)}
        </Text>
      ),
    },
    {
      title: '',
      key: 'actions',
      width: 50,
      render: (_: unknown, row: DataPoint) => (
        <Button
          size="small"
          icon={<EditOutlined />}
          type="text"
          onClick={() => {
            setWriteModal({ open: true, ref: row.reference, currentValue: row.value })
            setWriteValue(formatValue(row.value))
          }}
        />
      ),
    },
  ]

  return (
    <Layout style={{ height: 'calc(100vh - 0px)', background: '#f0f2f5' }}>
      {/* Left: Device tree */}
      <Sider
        width={240}
        style={{ background: '#fff', borderRight: '1px solid #f0f0f0', overflow: 'auto', padding: '12px 0' }}
      >
        <div style={{ padding: '0 12px 8px', fontWeight: 600, fontSize: 13, color: '#333' }}>
          Device Tree
        </div>
        {devicesQuery.isLoading ? (
          <div style={{ padding: 16 }}><Spin size="small" /></div>
        ) : (
          <Tree
            treeData={treeData}
            onSelect={onTreeSelect}
            defaultExpandAll={false}
            style={{ fontSize: 12 }}
          />
        )}
      </Sider>

      {/* Right: Data table */}
      <Content style={{ padding: 16, overflow: 'auto' }}>
        <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Input
              placeholder="Search references…"
              prefix={<SearchOutlined />}
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1) }}
              style={{ width: 280 }}
              allowClear
            />
            {(selectedLD || selectedLN) && (
              <Tag closable onClose={() => { setSelectedLD(''); setSelectedLN(''); setPage(1) }}>
                {selectedLN ? `${selectedLD} / ${selectedLN}` : selectedLD}
              </Tag>
            )}
          </Space>
          <Space>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {dpQuery.data?.total ?? 0} attributes
            </Text>
            <Button
              icon={<ReloadOutlined />}
              size="small"
              onClick={() => qc.invalidateQueries({ queryKey: ['datapoints'] })}
            />
          </Space>
        </Space>

        {dpQuery.isError && (
          <Alert type="error" message="Failed to load data points" style={{ marginBottom: 12 }} />
        )}

        <Table
          dataSource={dpQuery.data?.items ?? []}
          columns={columns}
          rowKey="reference"
          size="small"
          loading={dpQuery.isFetching}
          scroll={{ x: 600 }}
          pagination={{
            current: page,
            pageSize,
            total: dpQuery.data?.total ?? 0,
            showSizeChanger: true,
            pageSizeOptions: ['50', '100', '200'],
            showTotal: (t) => `${t} total`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps) },
          }}
        />
      </Content>

      {/* Write Value Modal */}
      <Modal
        title={`Write Value`}
        open={writeModal.open}
        onCancel={() => setWriteModal({ open: false, ref: '', currentValue: null })}
        onOk={() => writeMut.mutate({ ref: writeModal.ref, value: writeValue })}
        confirmLoading={writeMut.isPending}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text type="secondary" style={{ fontSize: 12, wordBreak: 'break-all' }}>
            {writeModal.ref}
          </Text>
          <Text style={{ fontSize: 12 }}>
            Type: <Tag>{writeModal.currentValue?.type ?? 'UNKNOWN'}</Tag>
            Current: <Text code>{formatValue(writeModal.currentValue)}</Text>
          </Text>
          <Input
            value={writeValue}
            onChange={(e) => setWriteValue(e.target.value)}
            placeholder="New value"
            autoFocus
          />
          {writeMut.isError && (
            <Alert type="error" message={(writeMut.error as Error)?.message} />
          )}
        </Space>
      </Modal>
    </Layout>
  )
}
