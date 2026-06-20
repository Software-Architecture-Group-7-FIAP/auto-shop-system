import { Component, Input, OnChanges } from '@angular/core';
import { Invoice, Priority, ServiceOrder } from '../../../model/models';
import { ServiceOrderService } from '../../../service/service-order.service';
import { ServiceOrdersComponent } from '../service-orders.component';

@Component({
  selector: 'app-service-order-detail',
  templateUrl: './service-order-detail.component.html',
  styleUrls: ['./service-order-detail.component.css'],
})
export class ServiceOrderDetailComponent implements OnChanges {
  @Input() serviceOrderId!: number;

  serviceOrder: ServiceOrder | undefined;
  mechanicName = '';
  selectedPriority: Priority = Priority.NORMAL;
  priorityValues = Object.values(Priority);
  lastInvoice: Invoice | null = null;
  actionMessage = '';

  constructor(
    private serviceOrderService: ServiceOrderService,
    private parent: ServiceOrdersComponent
  ) {}

  ngOnChanges(): void {
    if (this.serviceOrderId) {
      this.actionMessage = '';
      this.lastInvoice = null;
      this.loadServiceOrder();
    }
  }

  loadServiceOrder(): void {
    this.serviceOrderService.getById(this.serviceOrderId).subscribe((data) => {
      this.serviceOrder = data;
      this.mechanicName = data.mechanic_name || '';
      this.selectedPriority = data.priority;
    });
  }

  assignMechanic(): void {
    const name = this.mechanicName.trim();
    if (!name) {
      return;
    }
    this.serviceOrderService.assignMechanic(this.serviceOrderId, name).subscribe((updated) => {
      this.serviceOrder = updated;
      this.parent.updateServiceOrderInList(updated);
    });
  }

  setPriority(): void {
    this.serviceOrderService.setPriority(this.serviceOrderId, this.selectedPriority).subscribe((updated) => {
      this.serviceOrder = updated;
      this.parent.updateServiceOrderInList(updated);
    });
  }

  sendEmail(): void {
    this.serviceOrderService.sendEmail(this.serviceOrderId).subscribe((response) => {
      this.actionMessage = response.message;
    });
  }

  createInvoice(): void {
    this.serviceOrderService.createInvoice(this.serviceOrderId).subscribe((invoice) => {
      this.lastInvoice = invoice;
      this.actionMessage = `Fatura #${invoice.id} criada — R$ ${invoice.amount.toFixed(2)}`;
    });
  }

  deliver(): void {
    this.serviceOrderService.deliver(this.serviceOrderId).subscribe((updated) => {
      this.serviceOrder = updated;
      this.parent.updateServiceOrderInList(updated);
      this.actionMessage = 'Ordem de serviço entregue.';
    });
  }
}
