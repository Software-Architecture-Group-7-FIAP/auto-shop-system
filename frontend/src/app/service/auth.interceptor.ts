import { Injectable } from '@angular/core';
import {
  HttpEvent,
  HttpHandler,
  HttpInterceptor,
  HttpRequest,
} from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable()
export class AuthInterceptor implements HttpInterceptor {
  private readonly csrfCookie = 'oficina_csrf';

  private apiRequestUrl(url: string): string | null {
    try {
      const parsed = new URL(url, window.location.origin);
      if (
        parsed.origin !== window.location.origin ||
        !parsed.pathname.startsWith('/api/v1/')
      ) {
        return null;
      }

      // CloudFront keeps the browser request same-origin and selects hml/prd
      // through the stage-specific API origin configured on each distribution.
      return parsed.toString();
    } catch {
      return null;
    }
  }

  private csrfToken(): string | null {
    const entry = document.cookie
      .split('; ')
      .find((value) => value.startsWith(`${this.csrfCookie}=`));
    return entry ? decodeURIComponent(entry.substring(this.csrfCookie.length + 1)) : null;
  }

  intercept(req: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    const apiUrl = this.apiRequestUrl(req.url);
    if (!apiUrl) {
      return next.handle(req);
    }

    const headers: Record<string, string> = {};
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
      const csrf = this.csrfToken();
      if (csrf) {
        headers['X-CSRF-Token'] = csrf;
      }
    }
    return next.handle(
      req.clone({
        url: apiUrl,
        withCredentials: true,
        setHeaders: headers,
      })
    );
  }
}
