import { HttpErrorResponse } from '@angular/common/http';

export function extractApiErrorMessage(
  error: HttpErrorResponse,
  fallback = 'Não foi possível concluir a operação.'
): string {
  const detail = error.error?.detail;
  if (typeof detail === 'string') {
    return detail.replace(/^Dados inválidos:\s*/i, '').trim();
  }
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item: { msg?: string; loc?: (string | number)[] }) => {
        const field = item.loc?.length ? String(item.loc[item.loc.length - 1]) : '';
        const msg = item.msg ?? 'Valor inválido';
        return field ? `${field}: ${msg}` : msg;
      })
      .join('; ');
  }
  if (error.status === 0) {
    return 'Não foi possível conectar à API. Verifique se o servidor está rodando na porta 8000.';
  }
  if (error.status === 409) {
    return typeof detail === 'string' ? detail : 'Registro em conflito com dados existentes.';
  }
  return fallback;
}
