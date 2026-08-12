import type { ProviderInfo } from '../../../api/types';
import { partitionOpenRouterModels } from '../utils/providerModels';

export function ModelSelect({
  pid,
  info,
  onSaveModel,
}: {
  pid: string;
  info: ProviderInfo;
  onSaveModel: (pid: string, model: string) => void;
}) {
  const models = info.models || [];

  if (pid === 'openrouter') {
    const { free, paid } = partitionOpenRouterModels(models);
    return (
      <div className="model-row">
        <label>Model</label>
        <select
          value={info.model}
          disabled={!info.key_set}
          onChange={e => onSaveModel(pid, e.target.value)}
          onClick={e => e.stopPropagation()}
        >
          <optgroup label="Free">
            {free.map(m => <option key={m} value={m}>{m}</option>)}
          </optgroup>
          <optgroup label="Paid">
            {paid.map(m => <option key={m} value={m}>{m}</option>)}
          </optgroup>
        </select>
      </div>
    );
  }

  return (
    <div className="model-row">
      <label>Model</label>
      <select
        value={info.model}
        disabled={!info.key_set}
        onChange={e => onSaveModel(pid, e.target.value)}
        onClick={e => e.stopPropagation()}
      >
        {models.map(m => <option key={m} value={m}>{m}</option>)}
      </select>
    </div>
  );
}
