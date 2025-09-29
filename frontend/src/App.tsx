import { Link, NavLink, Outlet, Route, Routes, Navigate } from 'react-router-dom'
import {
  ActionIcon,
  Affix,
  AppShell,
  Burger,
  Container,
  Group,
  Text,
  Title,
  useComputedColorScheme,
  useMantineColorScheme,
  useMantineTheme,
} from '@mantine/core'
import { IconDna, IconMoon, IconSun } from '@tabler/icons-react'
import { useDisclosure } from '@mantine/hooks'
import { LandingPage } from './pages/LandingPage'
import { JobDetailPage } from './pages/JobDetailPage'
import { PreviousRunsPage } from './pages/PreviousRunsPage'

function AppLayout() {
  const theme = useMantineTheme()
  const [opened, { toggle, close }] = useDisclosure(false)
  const { setColorScheme } = useMantineColorScheme()
  const computedColorScheme = useComputedColorScheme('light', { getInitialValueInEffect: true })
  const isDark = computedColorScheme === 'dark'

  const links = [
    { to: '/', label: 'Design' },
    { to: '/jobs', label: 'Previous runs' },
  ]

  return (
    <AppShell
      header={{ height: 72 }}
      padding="xl"
    >
      <AppShell.Header>
        <Group justify="space-between" px="md" h="100%">
          <Group>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Toggle navigation" />
            <Link
              to="/"
              onClick={close}
              style={{
                textDecoration: 'none',
                color: 'inherit',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <Group gap="sm">
                <IconDna size={28} color={theme.colors.blue[6]} />
                <div>
                  <Title order={4}>CRISPR Design Tool</Title>
                  <Text size="sm" c="dimmed">MVP workflow for guide enumeration</Text>
                </div>
              </Group>
            </Link>
          </Group>
          <Group gap="lg" visibleFrom="sm">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                style={({ isActive }) => ({
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? theme.colors.blue[6] : theme.colors.gray[7],
                  textDecoration: 'none',
                })}
              >
                {link.label}
              </NavLink>
            ))}
          </Group>
        </Group>
      </AppShell.Header>


      <AppShell.Main>
        <Container size="lg" py="xl">
          <Outlet />
        </Container>
      </AppShell.Main>

      <Affix position={{ bottom: 24, right: 24 }}>
        <ActionIcon
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          variant="filled"
          size="lg"
          radius="xl"
          color="blue"
          onClick={() => setColorScheme(isDark ? 'light' : 'dark')}
        >
          {isDark ? <IconSun size={20} /> : <IconMoon size={20} />}
        </ActionIcon>
      </Affix>
    </AppShell>
  )
}

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<LandingPage />} />
        <Route path="jobs" element={<PreviousRunsPage />} />
        <Route path="jobs/:jobId" element={<JobDetailPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
