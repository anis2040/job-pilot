import { BackButton } from '../../components/layout/BackButton';
import { LoadErrorState } from '../../components/ui/LoadErrorState';
import { useAiSettings } from './hooks/useAiSettings';
import { ActiveBanner } from './components/ActiveBanner';
import { ProviderCard } from './components/ProviderCard';
import { SemanticMatchCard } from './components/SemanticMatchCard';

export default function AiSettingsPage() {
  const {
    data,
    preferred,
    loadError,
    retryLoad,
    selectProvider,
    saveKey,
    saveModel,
    testProvider,
    toggleSemantic,
  } = useAiSettings();

  if (loadError) {
    return <LoadErrorState title="Couldn't load AI settings" onRetry={retryLoad} />;
  }

  if (!data) {
    return (
      <div className="page-loading">
        <span className="spinner" />
      </div>
    );
  }

  return (
    <>
      <header style={{ padding: 'var(--space-4) var(--space-8)', borderBottom: '1px solid var(--border-faint)', display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
        <BackButton fallbackTo="/" fallbackLabel="Home" className="topbar-back" style={{ color: 'var(--blue-light)' }} />
        <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-white)' }}>⚡ AI Settings</h1>
      </header>

      <main className="page page-enter" id="main-content">
        <div className="page-header">
          <h2>AI Model Settings</h2>
          <p>Click a provider card to switch. Configure API keys and models per provider below.</p>
        </div>

        <ActiveBanner data={data} />

        {Object.entries(data.providers).map(([pid, info]) => (
          <ProviderCard
            key={pid}
            pid={pid}
            info={info}
            isPreferred={preferred === pid}
            onSelect={selectProvider}
            onSaveKey={saveKey}
            onSaveModel={saveModel}
            onTest={testProvider}
          />
        ))}

        <SemanticMatchCard data={data} onToggle={toggleSemantic} />
      </main>
    </>
  );
}
