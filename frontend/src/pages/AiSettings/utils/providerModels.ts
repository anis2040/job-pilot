export function partitionOpenRouterModels(models: string[]) {
  const free = models.filter(m => m.endsWith(':free'));
  const paid = models.filter(m => !m.endsWith(':free'));
  return { free, paid };
}
