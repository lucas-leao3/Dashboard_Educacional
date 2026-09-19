import { NavLink, useLocation } from 'react-router-dom';

interface NavItem {
  label: string;
  to: string;
  icon: React.ReactNode;
  /** Prefixos de rota que também mantêm o item ativo (ex.: Polos ⊃ /polo, /aluno). */
  prefixos?: string[];
}

// Ícones SVG idênticos aos da imagem de referência
const IconGrid = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
    <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
  </svg>
);

const IconBarChart = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/>
    <line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/>
  </svg>
);

const IconTrendingUp = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
    <polyline points="17 6 23 6 23 12"/>
  </svg>
);

const IconSparkles = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m11.314 11.314l.707-.707M12 5a7 7 0 0 0-7 7h14a7 7 0 0 0-7-7z"/>
    <path d="M5 12a7 7 0 0 0 14 0" strokeDasharray="3 3"/>
  </svg>
);

const IconHelp = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
    <line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
);

const IconLogout = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/>
    <line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
);

const IconMap = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
  </svg>
);

const IconUpload = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
  </svg>
);

interface Grupo { titulo: string; itens: NavItem[] }

// Navegação principal segue Polo → Turma → Aluno → Perfil (doc de alinhamento, item 3).
const grupos: Grupo[] = [
  {
    titulo: 'Navegação',
    itens: [
      { label: 'Polos', to: '/', icon: <IconMap />, prefixos: ['/polo/', '/aluno/'] },
      { label: 'Dados', to: '/dados', icon: <IconUpload /> },
    ],
  },
  {
    titulo: 'Análises',
    itens: [
      { label: 'Bidimensional', to: '/analises/bidimensional', icon: <IconGrid /> },
      { label: 'Distribuição',  to: '/analises/distribuicao', icon: <IconBarChart /> },
      { label: 'Longitudinal',  to: '/analises/longitudinal', icon: <IconTrendingUp /> },
      { label: 'IA Chat',       to: '/ia-chat', icon: <IconSparkles /> },
    ],
  },
];

interface SidebarProps {
  aberto?: boolean;
  onFechar?: () => void;
}

export default function Sidebar({ aberto = false, onFechar }: SidebarProps) {
  const { pathname } = useLocation();
  const ativoPorPrefixo = (item: NavItem) => item.prefixos?.some((p) => pathname.startsWith(p)) ?? false;
  return (
    <aside
      className={`fixed inset-y-0 left-0 z-30 flex flex-col h-screen w-64 shrink-0 bg-white border-r border-slate-100 font-sans transition-transform duration-200 md:static md:translate-x-0 ${aberto ? 'translate-x-0 shadow-2xl' : '-translate-x-full'}`}
      aria-label="Menu principal"
    >
      {/* Brand / Logo */}
      <div className="px-6 py-7">
        <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">PainelAcadêmico</h1>
        <p className="text-xs text-slate-400 font-medium mt-0.5">V1.0</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 space-y-5 overflow-y-auto">
        {grupos.map((grupo) => (
          <div key={grupo.titulo}>
            <p className="px-4 mb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">{grupo.titulo}</p>
            <div className="space-y-1.5">
              {grupo.itens.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  onClick={onFechar}
                  className={({ isActive }) =>
                    `flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 cursor-pointer ${
                      isActive || ativoPorPrefixo(item)
                        ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                        : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'
                    }`
                  }
                >
                  {item.icon}
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer Actions */}
      <div className="px-4 pb-6 pt-4 border-t border-slate-100/80 space-y-1.5">
        <button className="flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-semibold text-slate-500 hover:bg-slate-50 hover:text-slate-850 transition-all duration-200 w-full text-left cursor-pointer">
          <IconHelp />
          <span>Support</span>
        </button>
        <button className="flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-semibold text-slate-500 hover:bg-slate-50 hover:text-slate-850 transition-all duration-200 w-full text-left cursor-pointer">
          <IconLogout />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}
