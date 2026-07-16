import './index.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'

// Placeholder para rotas futuras
function EmConstrucao({ titulo }: { titulo: string }) {
  return (
    <div className="flex h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="text-center">
        <p className="text-6xl mb-4">🚧</p>
        <h1 className="text-2xl font-bold text-slate-700">{titulo}</h1>
        <p className="text-slate-400 mt-2">Em construção...</p>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard tipo="bidimensional" />} />
        <Route path="/distribuicao" element={<Dashboard tipo="distribuicao" />} />
        <Route path="/longitudinal"  element={<EmConstrucao titulo="Longitudinal" />} />
        <Route path="/ia-chat"       element={<EmConstrucao titulo="IA Chat" />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
