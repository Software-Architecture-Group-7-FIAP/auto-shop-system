import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../service/auth.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css'],
})
export class LoginComponent implements OnInit {
  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    if (this.authService.isLoggedIn()) {
      this.router.navigate(['/menu']);
    }
  }

  login(data: { username: string; password: string }): void {
    this.authService
      .login({ username: data.username.trim(), password: data.password })
      .subscribe(() => {
        this.router.navigate(['/menu']);
      });
  }
}
