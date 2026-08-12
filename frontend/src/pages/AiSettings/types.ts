export type KeyAlertKind = 'ok' | 'err' | 'neutral';

export interface KeyAlert {
  kind: KeyAlertKind;
  text: string;
}

export interface TestResult {
  ok: boolean;
  msg: string;
}

export interface ProviderTestResponse {
  ok: boolean;
  model?: string;
  latency_ms?: number;
  error?: string;
}
