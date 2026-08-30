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
  includeClosed = false;
  page = 1;
  readonly pageSize = 20;
  total = 0;
  totalPages = 0;
  isLoading = false;

  constructor(private serviceOrderService: ServiceOrderService) {}

  ngOnInit(): void {
    this.loadServiceOrders();
  }

  loadServiceOrders(): void {
    this.isLoading = true;
    this.serviceOrderService
      .getAll({
        status: this.selectedStatus || undefined,
        includeClosed: this.includeClosed,
        page: this.page,
        pageSize: this.pageSize,
      })
      .subscribe({
        next: (data) => {
          this.serviceOrders = data.items;
          this.total = data.total;
          this.totalPages = data.total_pages;
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

  applyFilters(): void {
    this.page = 1;
    this.loadServiceOrders();
  }

  goToPage(page: number): void {
    if (page < 1 || (this.totalPages && page > this.totalPages) || page === this.page) {
      return;
    }
    this.page = page;
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
