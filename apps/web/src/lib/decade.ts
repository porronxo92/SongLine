/** Variable CSS del color de la década (decoración; el año siempre va en texto). */
export function decadeVar(year: number): string {
  if (year < 1960) return 'var(--decade-50)';
  if (year < 1970) return 'var(--decade-60)';
  if (year < 1980) return 'var(--decade-70)';
  if (year < 1990) return 'var(--decade-80)';
  if (year < 2000) return 'var(--decade-90)';
  if (year < 2010) return 'var(--decade-00)';
  if (year < 2020) return 'var(--decade-10)';
  return 'var(--decade-20)';
}

/** Etiqueta de década para la carta grande: `AÑOS 90`. */
export function decadeLabel(year: number): string {
  const d = Math.floor(year / 10) * 10;
  return d < 1950 ? 'Antes de 1950' : `Años ${String(d % 100).padStart(2, '0')}`;
}
