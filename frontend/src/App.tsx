import { Route, Routes } from 'react-router-dom'
import AppShell from './components/shell/AppShell'
import { TopBar } from './components/shell/TopBar'
import FloorPage from './pages/Floor'

function Placeholder({ title }: { title: string }) {
  return (
    <>
      <TopBar crumbs={[title]} />
      <section className="px-7 pt-7 pb-7">
        <h1 className="text-[28px] font-semibold leading-[1.15] tracking-[-0.025em]">{title}</h1>
      </section>
    </>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<FloorPage />} />
        <Route path="tanks" element={<Placeholder title="Tanks" />} />
        <Route path="checks" element={<Placeholder title="Checks" />} />
        <Route path="decisions" element={<Placeholder title="Decisions" />} />
        <Route path="photos" element={<Placeholder title="Photo library" />} />
        <Route path="*" element={<Placeholder title="Not found" />} />
      </Route>
    </Routes>
  )
}
