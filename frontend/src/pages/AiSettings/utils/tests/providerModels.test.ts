import { describe, expect, it } from 'vitest';
import { partitionOpenRouterModels } from '@/pages/AiSettings/utils/providerModels';

describe('partitionOpenRouterModels', () => {
  it('splits free and paid models', () => {
    const models = [
      'google/gemma-4-31b-it:free',
      'nvidia/nemotron-3-super-120b-a12b:free',
      'anthropic/claude-sonnet-4.5',
      'openai/gpt-4o',
    ];
    expect(partitionOpenRouterModels(models)).toEqual({
      free: ['google/gemma-4-31b-it:free', 'nvidia/nemotron-3-super-120b-a12b:free'],
      paid: ['anthropic/claude-sonnet-4.5', 'openai/gpt-4o'],
    });
  });

  it('handles empty list', () => {
    expect(partitionOpenRouterModels([])).toEqual({ free: [], paid: [] });
  });
});
