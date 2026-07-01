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
import { catchError } from 'rxjs/operators';
import { AuthService } from './auth.service';

@Injectable()
export class HttpErrorInterceptor implements HttpInterceptor {
  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  intercept(req: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    return next.handle(req).pipe(
      catchError((error: HttpErrorResponse) => {
        if (error.status === 401 && this.isProtectedApiRequest(req.url)) {
          this.authService.logout();
          if (this.router.url !== '/login') {
            this.router.navigate(['/login']);
          }
        }

        let message = error.message;
        if (error.status === 401 && this.isProtectedApiRequest(req.url)) {
          message =
            'Sessão expirada ou inválida. Faça login novamente (use apenas uma API: local :8000 ou Docker :8001).';
        } else if (error.error?.detail) {
          message = typeof error.error.detail === 'string'
            ? error.error.detail
            : JSON.stringify(error.error.detail);
        }
        if (!req.context.get(SKIP_GLOBAL_ERROR_ALERT)) {
          alert(message);
        }
        return throwError(() => error);
      })
    );
  }

  private isProtectedApiRequest(url: string): boolean {
    return url.includes('/api/v1/admin/');
  }
}

export const SKIP_GLOBAL_ERROR_ALERT = new HttpContextToken<boolean>(() => false);
