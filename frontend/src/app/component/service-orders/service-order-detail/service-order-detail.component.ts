import { Component, Input, OnChanges } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import {
  Invoice,
  InvoiceStatus,
  Priority,
  ServiceOrder,
  ServiceOrderStatus,
  ServiceOrderUpdate,
} from '../../../model/models';
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
  selectedStatus: ServiceOrderStatus = ServiceOrderStatus.AGUARDANDO_APROVACAO;
  priorityValues = Object.values(Priority);
  statusValues = Object.values(ServiceOrderStatus);
  invoice: Invoice | null = null;
  actionMessage = '';
  errorMessage = '';
  isSaving = false;
  isSendingEmail = false;
  isStarting = false;
  isFinishing = false;
  isCreatingInvoice = false;
  isPayingInvoice = false;
  readonly serviceOrderStatus = ServiceOrderStatus;
  readonly invoiceStatus = InvoiceStatus;

  constructor(
    private serviceOrderService: ServiceOrderService,
    private parent: ServiceOrdersComponent
  ) {}

  ngOnChanges(): void {
    if (this.serviceOrderId) {
      this.actionMessage = '';
      this.errorMessage = '';
      this.invoice = null;
      this.loadServiceOrder();
    }
  }

  loadServiceOrder(): void {
    this.serviceOrderService.getById(this.serviceOrderId).subscribe((data) => {
      this.serviceOrder = data;
      this.mechanicName = data.mechanic_name || '';
      this.selectedPriority = data.priority;
      this.selectedStatus = data.status;
      this.loadInvoice();
    });
  }

  loadInvoice(): void {
    if (!this.shouldShowBillingSection()) {
      this.invoice = null;
      return;
    }
    this.serviceOrderService.getInvoice(this.serviceOrderId).subscribe({
      next: (invoice) => {
        this.invoice = invoice;
      },
      error: () => {
        this.invoice = null;
      },
    });
  }

  saveChanges(): void {
    const name = this.mechanicName.trim();
    const payload: ServiceOrderUpdate = {
      priority: this.selectedPriority,
      status: this.selectedStatus,
    };
    if (name) {
      payload.mechanic_name = name;
    }
    this.isSaving = true;
    this.errorMessage = '';
    this.serviceOrderService.update(this.serviceOrderId, payload).subscribe({
      next: (updated) => {
        this.serviceOrder = updated;
        this.selectedStatus = updated.status;
        this.parent.updateServiceOrderInList(updated);
        this.actionMessage = 'Ordem de serviço atualizada.';
        this.loadInvoice();
      },
      complete: () => {
        this.isSaving = false;
      },
      error: () => {
        this.isSaving = false;
      },
    });
  }

  sendEmail(): void {
    this.isSendingEmail = true;
    this.serviceOrderService.sendEmail(this.serviceOrderId).subscribe({
      next: (response) => {
        this.actionMessage = response.message;
      },
      complete: () => {
        this.isSendingEmail = false;
      },
      error: () => {
        this.isSendingEmail = false;
      },
    });
  }

  canStart(): boolean {
    if (!this.serviceOrder) {
      return false;
    }
    const hasMechanic = Boolean(this.serviceOrder.mechanic_name?.trim());
    return (
      hasMechanic &&
      [
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ServiceOrderStatus.EM_DIAGNOSTICO,
      ].includes(this.serviceOrder.status)
    );
  }

  shouldShowStart(): boolean {
    return Boolean(
      this.serviceOrder &&
      [
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ServiceOrderStatus.EM_DIAGNOSTICO,
      ].includes(this.serviceOrder.status)
    );
  }

  startService(): void {
    if (!this.canStart()) {
      this.actionMessage = 'Mecânico obrigatório para iniciar.';
      return;
    }
    this.isStarting = true;
    this.serviceOrderService.startServiceOrder(this.serviceOrderId).subscribe({
      next: (updated) => {
        this.serviceOrder = updated;
        this.parent.updateServiceOrderInList(updated);
        this.actionMessage = 'Serviço iniciado.';
      },
      complete: () => {
        this.isStarting = false;
      },
      error: () => {
        this.isStarting = false;
      },
    });
  }

  canFinish(): boolean {
    return this.serviceOrder?.status === ServiceOrderStatus.EM_EXECUCAO;
  }

  finishService(): void {
    if (!this.canFinish()) {
      return;
    }
    this.isFinishing = true;
    this.serviceOrderService.finishServiceOrder(this.serviceOrderId).subscribe({
      next: (updated) => {
        this.serviceOrder = updated;
        this.parent.updateServiceOrderInList(updated);
        this.actionMessage = 'Serviço finalizado.';
      },
      complete: () => {
        this.isFinishing = false;
      },
      error: () => {
        this.isFinishing = false;
      },
    });
  }

  shouldShowBillingSection(): boolean {
    return Boolean(
      this.serviceOrder &&
      [
        ServiceOrderStatus.FINALIZADA,
        ServiceOrderStatus.ENTREGUE,
      ].includes(this.serviceOrder.status)
    );
  }

  private setErrorMessage(error: unknown, fallback: string): void {
    const httpError = error as HttpErrorResponse;
    this.errorMessage =
      (typeof httpError?.error?.detail === 'string' && httpError.error.detail) ||
      fallback;
  }

  canCreateInvoice(): boolean {
    return this.serviceOrder?.status === ServiceOrderStatus.FINALIZADA && !this.invoice;
  }

  canPayInvoice(): boolean {
    return (
      this.serviceOrder?.status === ServiceOrderStatus.FINALIZADA &&
      this.invoice?.status === InvoiceStatus.PENDING
    );
  }

  createInvoice(): void {
    if (!this.canCreateInvoice()) {
      return;
    }
    this.isCreatingInvoice = true;
    this.errorMessage = '';
    this.serviceOrderService.createInvoice(this.serviceOrderId).subscribe({
      next: (invoice) => {
        this.invoice = invoice;
        this.actionMessage = `Fatura #${invoice.id} criada — R$ ${invoice.amount.toFixed(2)}`;
      },
      complete: () => {
        this.isCreatingInvoice = false;
      },
      error: (error) => {
        this.isCreatingInvoice = false;
        this.setErrorMessage(error, 'Não foi possível gerar a fatura.');
      },
    });
  }

  payInvoice(): void {
    if (!this.invoice || !this.canPayInvoice()) {
      return;
    }
    this.isPayingInvoice = true;
    this.errorMessage = '';
    this.serviceOrderService.payInvoice(this.invoice.id).subscribe({
      next: (invoice) => {
        this.invoice = invoice;
        this.loadServiceOrder();
        this.actionMessage = 'Pagamento registrado. OS entregue.';
      },
      complete: () => {
        this.isPayingInvoice = false;
      },
      error: (error) => {
        this.isPayingInvoice = false;
        this.setErrorMessage(error, 'Não foi possível registrar o pagamento.');
      },
    });
  }
}
