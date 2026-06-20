import { Component, OnInit } from '@angular/core';
import { ServiceOrder } from '../../model/models';
import { ServiceOrderService } from '../../service/service-order.service';

@Component({
  selector: 'app-service-orders',
  templateUrl: './service-orders.component.html',
  styleUrls: ['./service-orders.component.css'],
})
export class ServiceOrdersComponent implements OnInit {
  serviceOrders: ServiceOrder[] = [];
  selectedServiceOrderId: number | undefined;

  constructor(private serviceOrderService: ServiceOrderService) {}

  ngOnInit(): void {
    this.serviceOrderService.getAll().subscribe((data) => {
      this.serviceOrders = data.sort((a, b) => a.id - b.id);
    });
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
