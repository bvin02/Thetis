import { Link, Route, Routes } from 'react-router-dom'
import AppShell from './components/shell/AppShell'
import { TopBar } from './components/shell/TopBar'
import { EmptyState } from './components/ui'
import AdvisorPage from './pages/Advisor'
import CheckDetailPage from './pages/CheckDetail'
import ChecksListPage from './pages/ChecksList'
import DecisionsPage from './pages/Decisions'
import FloorPage from './pages/Floor'
import NewCheckPage from './pages/NewCheck'
import PhotoLibraryPage from './pages/PhotoLibrary'
import TankPage from './pages/TankPage'
import TanksListPage from './pages/TanksList'

function NotFound() {
  return (
    <>
      <TopBar crumbs={['Not found']} />
      <EmptyState title="There's nothing at this address">
        <Link to="/" className="text-brand underline-offset-2">Back to the Floor</Link>
      </EmptyState>
    </>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<FloorPage />} />
        <Route path="advisor" element={<AdvisorPage />} />
        <Route path="tanks" element={<TanksListPage />} />
        <Route path="tanks/:id" element={<TankPage />} />
        <Route path="checks" element={<ChecksListPage />} />
        <Route path="checks/new" element={<NewCheckPage />} />
        <Route path="checks/:id" element={<CheckDetailPage />} />
        <Route path="decisions" element={<DecisionsPage />} />
        <Route path="photos" element={<PhotoLibraryPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
