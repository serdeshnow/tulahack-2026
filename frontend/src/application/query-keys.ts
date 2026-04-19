export const queryKeys = {
  catalog: (filters: unknown) => ['catalog', filters] as const,
  record: (audioId: string) => ['record', audioId] as const,
  status: (audioId: string) => ['record', audioId, 'status'] as const,
  transcript: (audioId: string, view: string) => ['record', audioId, 'transcript', view] as const,
  summary: (audioId: string) => ['record', audioId, 'summary'] as const,
  logs: (audioId: string) => ['record', audioId, 'logs'] as const,
  statsOverview: () => ['stats', 'overview'] as const,
  apiDocs: () => ['api-docs'] as const
}
