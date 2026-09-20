import { Link } from 'react-router-dom';

const IconAudioWave = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="12" y1="5" x2="12" y2="19" /><line x1="8" y1="9" x2="8" y2="15" />
    <line x1="16" y1="9" x2="16" y2="15" /><line x1="4" y1="11" x2="4" y2="13" /><line x1="20" y1="11" x2="20" y2="13" />
  </svg>
);

/** Botão flutuante de acesso ao IA Chat, compartilhado pelos cards de gráfico. */
export default function BotaoIA() {
  return (
    <Link
      to="/ia-chat"
      aria-label="Abrir IA Chat"
      title="Abrir IA Chat"
      className="absolute -bottom-6 -right-2 w-14 h-14 rounded-full flex items-center justify-center shadow-lg hover:shadow-xl hover:scale-110 active:scale-95 transition-all duration-200 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300"
      style={{ background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)', boxShadow: '0 8px 30px rgba(37, 99, 235, 0.35)' }}
    >
      <IconAudioWave />
    </Link>
  );
}
