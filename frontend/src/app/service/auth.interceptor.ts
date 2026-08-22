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

  private isApiRequest(url: string): boolean {
    const parsed = new URL(url, window.location.origin);
    return parsed.origin === window.location.origin && parsed.pathname.startsWith('/api/v1/');
  }

  private csrfToken(): string | null {
    const entry = document.cookie
      .split('; ')
      .find((value) => value.startsWith(`${this.csrfCookie}=`));
    return entry ? decodeURIComponent(entry.substring(this.csrfCookie.length + 1)) : null;
  }

  intercept(req: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    if (!this.isApiRequest(req.url)) {
      return next.handle(req);
    }

    const headers: Record<string, string> = {};
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
      const csrf = this.csrfToken();
      if (csrf) {
        headers['X-CSRF-Token'] = csrf;
      }
    }
    return next.handle(req.clone({ withCredentials: true, setHeaders: headers }));
  }
}
