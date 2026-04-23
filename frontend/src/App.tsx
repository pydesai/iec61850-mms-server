import { BrowserRouter, Routes, Route, Navigate, NavLink } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider, Layout, Menu, Typography, Badge, theme } from 'antd'
import {
  DashboardOutlined,
  DatabaseOutlined,
  ApiOutlined,
  FileTextOutlined,
  SettingOutlined,
  WifiOutlined,
} from '@ant-design/icons'
import Dashboard from './pages/Dashboard'
import DataBrowser from './pages/DataBrowser'
import Connections from './pages/Connections'
import Logs from './pages/Logs'
import Settings from './pages/Settings'
import { useWebSocket } from './hooks/useWebSocket'
import { useServerStore } from './store/serverStore'

const { Sider, Content } = Layout
const { Text } = Typography

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 2000 },
  },
})

const NAV_ITEMS = [
  { path: '/dashboard',    label: 'Dashboard',     icon: <DashboardOutlined /> },
  { path: '/data',         label: 'Data Browser',  icon: <DatabaseOutlined /> },
  { path: '/connections',  label: 'Connections',   icon: <ApiOutlined /> },
  { path: '/logs',         label: 'Logs',          icon: <FileTextOutlined /> },
  { path: '/settings',     label: 'Settings',      icon: <SettingOutlined /> },
]

function AppInner() {
  useWebSocket()
  const { status, wsConnected } = useServerStore()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={220}
        style={{ background: '#001529', position: 'sticky', top: 0, height: '100vh', overflowY: 'auto' }}
      >
        {/* Logo / Title */}
        <div style={{ padding: '20px 16px 12px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          <Text strong style={{ color: '#fff', fontSize: 14, display: 'block' }}>
            IEC 61850
          </Text>
          <Text style={{ color: 'rgba(255,255,255,0.45)', fontSize: 12 }}>
            MMS Simulator
          </Text>
        </div>

        {/* Server status indicator */}
        <div style={{ padding: '10px 16px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          <Badge
            status={status.running ? 'success' : 'error'}
            text={
              <Text style={{ color: 'rgba(255,255,255,0.65)', fontSize: 12 }}>
                {status.running ? `Running :${status.port}` : 'Stopped'}
              </Text>
            }
          />
          {status.running && (
            <div style={{ marginTop: 4 }}>
              <Badge
                count={status.connections}
                style={{ backgroundColor: status.connections > 0 ? '#52c41a' : '#999' }}
                showZero
              />
              <Text style={{ color: 'rgba(255,255,255,0.45)', fontSize: 11, marginLeft: 6 }}>
                clients
              </Text>
            </div>
          )}
        </div>

        {/* Navigation */}
        <Menu
          theme="dark"
          mode="inline"
          style={{ border: 'none', marginTop: 4 }}
          items={NAV_ITEMS.map(({ path, label, icon }) => ({
            key: path,
            icon,
            label: <NavLink to={path} style={{ color: 'inherit' }}>{label}</NavLink>,
          }))}
        />

        {/* WS connection indicator */}
        <div style={{ position: 'absolute', bottom: 12, left: 16 }}>
          <Badge
            status={wsConnected ? 'processing' : 'default'}
            text={
              <Text style={{ color: 'rgba(255,255,255,0.35)', fontSize: 10 }}>
                {wsConnected ? 'Live' : 'Reconnecting…'}
              </Text>
            }
          />
          <WifiOutlined style={{ color: 'rgba(255,255,255,0.25)', marginLeft: 8, fontSize: 10 }} />
        </div>
      </Sider>

      <Content style={{ background: '#f0f2f5', minHeight: '100vh', overflow: 'auto' }}>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard"   element={<Dashboard />} />
          <Route path="/data"        element={<DataBrowser />} />
          <Route path="/connections" element={<Connections />} />
          <Route path="/logs"        element={<Logs />} />
          <Route path="/settings"    element={<Settings />} />
          <Route path="*"            element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Content>
    </Layout>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        theme={{
          algorithm: theme.defaultAlgorithm,
          token: { colorPrimary: '#1677ff', borderRadius: 6 },
        }}
      >
        <BrowserRouter>
          <AppInner />
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  )
}
