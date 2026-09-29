import './index.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom'
import { DadosProvider } from './hooks/DadosProvider'
import Polos from './pages/Polos'
import Turmas from './pages/Turmas'
import Alunos from './pages/Alunos'
import Perfil from './pages/Perfil'
import Analises from './pages/Analises'
import Dados from './pages/Dados'
import IaChat from './pages/IaChat'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <DadosProvider>
        <Routes>
          {/* Navegação hierárquica: Polo → Turma → Aluno → Perfil */}
          <Route path="/" element={<Polos />} />
          <Route path="/polo/:polo" element={<Turmas />} />
          <Route path="/polo/:polo/turma/:turma" element={<Alunos />} />
          <Route path="/aluno/:matricula" element={<Perfil />} />

          {/* Inserção de lote + cobertura (docs/superpowers/specs/2026-09-18-tela-dados-lote-design.md) */}
          <Route path="/dados" element={<Dados />} />

          {/* Análises agregadas (gráficos do dashboard anterior) */}
          <Route path="/analises/bidimensional" element={<Analises tipo="bidimensional" />} />
          <Route path="/analises/distribuicao" element={<Analises tipo="distribuicao" />} />
          <Route path="/analises/longitudinal" element={<Analises tipo="longitudinal" />} />
          <Route path="/distribuicao" element={<Navigate to="/analises/distribuicao" replace />} />
          <Route path="/longitudinal" element={<Navigate to="/analises/longitudinal" replace />} />

          {/* Assistente de consultas (docs/superpowers/specs/2026-09-25-assistente-consultas-design.md) */}
          <Route path="/ia-chat" element={<IaChat />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </DadosProvider>
    </BrowserRouter>
  </StrictMode>,
)
