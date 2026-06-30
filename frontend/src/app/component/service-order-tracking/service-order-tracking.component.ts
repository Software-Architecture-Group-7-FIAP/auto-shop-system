import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ServiceOrderPublic } from '../../model/models';
import { ServiceOrderService } from '../../service/service-order.service';

@Component({
  selector: 'app-service-order-tracking',
  templateUrl: './service-order-tracking.component.html',
  styleUrls: ['./service-order-tracking.component.css'],
})
export class ServiceOrderTrackingComponent implements OnInit {
  token = '';
  serviceOrder: ServiceOrderPublic | null = null;
  isLoading = false;
  message = '';

  constructor(
    private route: ActivatedRoute,
    private serviceOrderService: ServiceOrderService
  ) {}

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (token) {
      this.token = token;
      this.track();
    }
  }

  track(): void {
    const token = this.token.trim();
    if (!token) {
      this.message = 'Informe o token de acompanhamento.';
      this.serviceOrder = null;
      return;
    }

    this.isLoading = true;
    this.message = '';
    this.serviceOrderService.trackPublic(token).subscribe({
      next: (serviceOrder) => {
        this.serviceOrder = serviceOrder;
      },
      complete: () => {
        this.isLoading = false;
      },
      error: () => {
        this.serviceOrder = null;
        this.message = 'Link de acompanhamento inválido.';
        this.isLoading = false;
      },
    });
  }
}
