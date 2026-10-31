import { Injectable } from '@angular/core';
import { CanActivate, Router } from '@angular/router';
import { Observable, map } from 'rxjs';
import { AuthService } from '../service/auth.service';

@Injectable({ providedIn: 'root' })
export class AuthGuard implements CanActivate {
  constructor(private authService: AuthService, private router: Router) {}

  canActivate(): Observable<boolean> {
    return this.authService.ensureSession().pipe(
      map((isAuthenticated) => {
        if (!isAuthenticated) {
          this.router.navigate(['/login']);
        }
        return isAuthenticated;
      })
    );
  }
}
