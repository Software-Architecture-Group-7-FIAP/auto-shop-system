import { Injectable } from '@angular/core';
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

@Injectable()
export class HttpErrorInterceptor implements HttpInterceptor {
  intercept(req: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    return next.handle(req).pipe(
      catchError((error: HttpErrorResponse) => {
        let message = error.message;
        if (error.error?.detail) {
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
}

export const SKIP_GLOBAL_ERROR_ALERT = new HttpContextToken<boolean>(() => false);
