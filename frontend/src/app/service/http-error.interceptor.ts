import { Injectable } from '@angular/core';
import { Router } from '@angular/router';
import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandler,
  HttpContextToken,
  HttpInterceptor,
  HttpRequest,
} from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { catchError } from 'rxjs/operators';
import { AuthService } from './auth.service';
import { NotificationService } from './notification.service';

@Injectable()
export class HttpErrorInterceptor implements HttpInterceptor {
  constructor(
    private authService: AuthService,
    private router: Router,
    private notifications: NotificationService
  ) {}

  intercept(req: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    return next.handle(req).pipe(
      catchError((error: HttpErrorResponse) => {
        if (
          error.status === 401 &&
          this.isProtectedApiRequest(req.url) &&
          !req.context.get(RETRIED_AFTER_REFRESH)
        ) {
          return this.authService.refresh().pipe(
            switchMap(() => next.handle(this.retryWithCurrentCsrf(req))),
            catchError((refreshError: HttpErrorResponse) => {
              this.authService.logout();
              if (this.router.url !== '/login') {
                this.router.navigate(['/login']);
              }
              return this.handleError(refreshError, req);
            })
          );
        }

        return this.handleError(error, req);
      })
    );
  }

  private handleError(error: HttpErrorResponse, req: HttpRequest<unknown>): Observable<never> {
    const isExpiredSession =
      error.status === 401 && this.isProtectedApiRequest(req.url);

    let message = error.message;
    if (isExpiredSession) {
      message = 'Sessão expirada ou inválida. Faça login novamente.';
    } else if (error.error?.detail) {
      message =
        typeof error.error.detail === 'string'
          ? error.error.detail
          : JSON.stringify(error.error.detail);
    }

    if (!req.context.get(SKIP_GLOBAL_ERROR_ALERT)) {
      if (isExpiredSession) {
        this.notifications.warning(message);
      } else {
        this.notifications.error(message);
      }
    }
    return throwError(() => error);
  }

  private isProtectedApiRequest(url: string): boolean {
    // Services declare relative URLs ('api/v1/admin/budgets'), so a raw
    // substring check for '/api/v1/admin/' never matches and the whole
    // silent-refresh path below would be dead code.
    try {
      const parsed = new URL(url, window.location.origin);
      return (
        parsed.origin === window.location.origin &&
        parsed.pathname.startsWith('/api/v1/admin/')
      );
    } catch {
      return false;
    }
  }

  private retryWithCurrentCsrf(req: HttpRequest<unknown>): HttpRequest<unknown> {
    const csrfCookie = document.cookie
      .split('; ')
      .find((value) => value.startsWith('oficina_csrf='));
    const csrf = csrfCookie
      ? decodeURIComponent(csrfCookie.substring('oficina_csrf='.length))
      : null;
    const headers: Record<string, string> = {};
    if (csrf && !['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
      headers['X-CSRF-Token'] = csrf;
    }
    return req.clone({
      context: req.context.set(RETRIED_AFTER_REFRESH, true),
      withCredentials: true,
      setHeaders: headers,
    });
  }
}

export const SKIP_GLOBAL_ERROR_ALERT = new HttpContextToken<boolean>(() => false);
const RETRIED_AFTER_REFRESH = new HttpContextToken<boolean>(() => false);
