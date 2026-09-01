import { Component, OnInit } from '@angular/core';
import { ServiceOrder, ServiceOrderStatus } from '../../model/models';
import { ServiceOrderService } from '../../service/service-order.service';

@Component({
  selector: 'app-service-orders',
  templateUrl: './service-orders.component.html',
  styleUrls: ['./service-orders.component.css'],
})
export class ServiceOrdersComponent implements OnInit {
  serviceOrders: ServiceOrder[] = [];
  selectedServiceOrderId: number | undefined;
  statusValues = Object.values(ServiceOrderStatus);
  selectedStatus = '';
  isLoading = false;

  constructor(private serviceOrderService: ServiceOrderService) {}

  ngOnInit(): void {
    this.loadServiceOrders();
  }

  loadServiceOrders(): void {
    this.isLoading = true;
    this.serviceOrderService.getAll(this.selectedStatus || undefined).subscribe({
      next: (data) => {
        this.serviceOrders = data.sort((a, b) => a.id - b.id);
        if (
          this.selectedServiceOrderId &&
          !this.serviceOrders.some((order) => order.id === this.selectedServiceOrderId)
        ) {
          this.selectedServiceOrderId = undefined;
        }
      },
      complete: () => {
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      },
    });
  }

  applyStatusFilter(): void {
    this.loadServiceOrders();
  }

  selectServiceOrder(id: number): void {
    this.selectedServiceOrderId = id;
  }

  toCreatingMode = (): void => {
    /* Ordens de serviço são criadas a partir de orçamentos aprovados */
  };

  updateServiceOrderInList(serviceOrder: ServiceOrder): void {
    const index = this.serviceOrders.findIndex((o) => o.id === serviceOrder.id);
    if (index >= 0) {
      this.serviceOrders[index] = serviceOrder;
    }
  }
}
