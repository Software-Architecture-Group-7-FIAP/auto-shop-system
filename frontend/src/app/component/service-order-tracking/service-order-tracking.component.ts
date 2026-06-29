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
  serviceOrderId = '';
  document = '';
  serviceOrder: ServiceOrderPublic | null = null;
  isLoading = false;
  message = '';

  constructor(
    private route: ActivatedRoute,
    private serviceOrderService: ServiceOrderService
  ) {}

  ngOnInit(): void {
    const id = this.route.snapshot.queryParamMap.get('serviceOrderId');
    if (id) {
      this.serviceOrderId = id;
    }
  }

  track(): void {
    const id = Number(this.serviceOrderId);
    const document = this.document.trim();
    if (!Number.isInteger(id) || id <= 0 || !document) {
      this.message = 'Informe ID da OS e CPF/CNPJ.';
      this.serviceOrder = null;
      return;
    }

    this.isLoading = true;
    this.message = '';
    this.serviceOrderService.trackPublic(id, document).subscribe({
      next: (serviceOrder) => {
        this.serviceOrder = serviceOrder;
      },
      complete: () => {
        this.isLoading = false;
      },
      error: () => {
        this.serviceOrder = null;
        this.message = 'OS não encontrada para este documento.';
        this.isLoading = false;
      },
    });
  }
}
