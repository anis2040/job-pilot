import type { AiSettings } from '../../../api/types';

export function SemanticMatchCard({
  data,
  onToggle,
}: {
  data: AiSettings;
  onToggle: (checked: boolean) => void;
}) {
  return (
    <div className="provider-card" id="semantic-card">
      <div className="card-header" style={{ cursor: 'default' }}>
        <div className="card-header-text">
          <h3>Smart job matching</h3>
          <div className="sub">Ranks jobs by overall fit using embeddings</div>
        </div>
        <label className="switch">
          <input
            type="checkbox"
            checked={data.semantic_match && data.embeddings_available}
            disabled={!data.embeddings_available}
            onChange={e => onToggle(e.target.checked)}
          />
          <span className="switch-slider" />
        </label>
      </div>
      <div className="card-body is-expanded">
        <p className="semantic-note">
          {!data.embeddings_available
            ? 'Requires a Gemini API key (the only provider here that offers embeddings). Without it, jobs are still matched by skill keywords.'
            : 'Ranks jobs by overall fit (semantic similarity between the job and your profile), on top of the skill-match chips. Cost: a fraction of a cent per job on a paid Gemini key, or free (rate-limited) on a free-tier key — computed once per job and cached.'}
        </p>
      </div>
    </div>
  );
}
