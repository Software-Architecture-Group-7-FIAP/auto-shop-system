import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, finalize, map, of, shareReplay, tap } from 'rxjs';
import { LoginRequest, SessionResponse } from '../model/models';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private authUrl = 'api/v1/auth';
  private currentUser: SessionResponse | null = null;
  private refreshInFlight: Observable<SessionResponse> | null = null;

  constructor(private http: HttpClient) {}

  login(credentials: LoginRequest): Observable<SessionResponse> {
    this.currentUser = null;
    this.refreshInFlight = null;
    return this.http
      .post<SessionResponse>(`${this.authUrl}/login`, credentials, { withCredentials: true })
      .pipe(tap((response) => (this.currentUser = response)));
  }

  refresh(): Observable<SessionResponse> {
    // Parallel 401s must share one rotation. Two concurrent POSTs would send
    // the same refresh cookie, and the server reads the second one as token
    // reuse and revokes the whole session family.
    if (!this.refreshInFlight) {
      this.refreshInFlight = this.http
        .post<SessionResponse>(`${this.authUrl}/refresh`, {}, { withCredentials: true })
        .pipe(
          tap((response) => (this.currentUser = response)),
          finalize(() => (this.refreshInFlight = null)),
          shareReplay({ bufferSize: 1, refCount: false })
        );
    }
    return this.refreshInFlight;
  }

  logout(): void {
    this.currentUser = null;
    this.refreshInFlight = null;
    this.http
      .post(`${this.authUrl}/logout`, {}, { withCredentials: true })
      .pipe(catchError(() => of(null)))
      .subscribe();
  }

  me(): Observable<SessionResponse> {
    return this.http
      .get<SessionResponse>(`${this.authUrl}/me`, { withCredentials: true })
      .pipe(tap((response) => (this.currentUser = response)));
  }

  ensureSession(): Observable<boolean> {
    if (this.currentUser) {
      return of(true);
    }
    return this.me().pipe(
      map(() => true),
      catchError(() => {
        return this.refresh().pipe(
          map(() => true),
          catchError(() => {
            this.currentUser = null;
            return of(false);
          })
        );
      })
    );
  }

  getUsername(): string | null {
    return this.currentUser?.username ?? null;
  }

  isLoggedIn(): boolean {
    return this.currentUser !== null;
  }
}
