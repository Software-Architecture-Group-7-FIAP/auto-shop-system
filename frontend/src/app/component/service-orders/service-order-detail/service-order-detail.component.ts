import { Component, Input, OnChanges } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import {
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
  mechanicChangeReason = '';
  selectedPriority: Priority = Priority.NORMAL;
  selectedStatus: ServiceOrderStatus = ServiceOrderStatus.AGUARDANDO_APROVACAO;
  statusOverrideReason = '';
  priorityValues = Object.values(Priority);
  statusValues = Object.values(ServiceOrderStatus);
  actionMessage = '';
  errorMessage = '';
  isSaving = false;
  isOverridingStatus = false;
  isSendingEmail = false;
  isStarting = false;
  isFinishing = false;
  readonly serviceOrderStatus = ServiceOrderStatus;

  constructor(
    private serviceOrderService: ServiceOrderService,
    private parent: ServiceOrdersComponent
  ) {}

  ngOnChanges(): void {
    if (this.serviceOrderId) {
      this.actionMessage = '';
      this.errorMessage = '';
      this.loadServiceOrder();
    }
  }

  loadServiceOrder(): void {
    this.serviceOrderService.getById(this.serviceOrderId).subscribe((data) => {
      this.serviceOrder = data;
      this.mechanicName = data.mechanic_name || '';
      this.mechanicChangeReason = '';
      this.selectedPriority = data.priority;
      this.selectedStatus = data.status;
    });
  }

  saveChanges(): void {
    this.actionMessage = '';
    this.errorMessage = '';
    const name = this.mechanicName.trim();
    const previousName = this.serviceOrder?.mechanic_name?.trim() || '';
    const isReassignment = Boolean(previousName && name && name !== previousName);
    if (isReassignment && !this.mechanicChangeReason.trim()) {
      this.errorMessage = 'Motivo obrigatório para trocar o mecânico.';
      return;
    }
    const payload: ServiceOrderUpdate = {
      priority: this.selectedPriority,
    };
    if (name) {
      payload.mechanic_name = name;
    }
    if (isReassignment) {
      payload.reason = this.mechanicChangeReason.trim();
    }
    this.isSaving = true;
    this.errorMessage = '';
    this.serviceOrderService.update(this.serviceOrderId, payload).subscribe({
      next: (updated) => {
        this.serviceOrder = updated;
        this.selectedStatus = updated.status;
        this.mechanicChangeReason = '';
        this.parent.updateServiceOrderInList(updated);
        this.actionMessage = 'Ordem de serviço atualizada.';
      },
      complete: () => {
        this.isSaving = false;
      },
      error: (error) => {
        this.isSaving = false;
        this.setErrorMessage(error, 'Não foi possível atualizar a ordem de serviço.');
      },
    });
  }

  overrideStatus(): void {
    this.actionMessage = '';
    this.errorMessage = '';
    const reason = this.statusOverrideReason.trim();
    if (!reason) {
      this.errorMessage = 'Motivo obrigatório para alterar status.';
      return;
    }
    this.isOverridingStatus = true;
    this.errorMessage = '';
    this.serviceOrderService
      .overrideStatus(this.serviceOrderId, {
        status: this.selectedStatus,
        reason,
      })
      .subscribe({
        next: (updated) => {
          this.serviceOrder = updated;
          this.selectedStatus = updated.status;
          this.statusOverrideReason = '';
          this.parent.updateServiceOrderInList(updated);
          this.actionMessage = 'Status da OS alterado por override administrativo.';
        },
        complete: () => {
          this.isOverridingStatus = false;
        },
        error: (error) => {
          this.isOverridingStatus = false;
          this.setErrorMessage(error, 'Não foi possível alterar o status.');
        },
      });
  }

  sendEmail(): void {
    this.isSendingEmail = true;
    this.actionMessage = '';
    this.errorMessage = '';
    this.serviceOrderService.sendEmail(this.serviceOrderId).subscribe({
      next: (response) => {
        this.actionMessage = response.message;
      },
      complete: () => {
        this.isSendingEmail = false;
      },
      error: (error) => {
        this.isSendingEmail = false;
        this.setErrorMessage(error, 'Não foi possível enviar o PDF por e-mail.');
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
      this.serviceOrder.status === ServiceOrderStatus.AGUARDANDO_INICIO
    );
  }

  shouldShowStart(): boolean {
    return Boolean(
      this.serviceOrder &&
      this.serviceOrder.status === ServiceOrderStatus.AGUARDANDO_INICIO
    );
  }

  startService(): void {
    if (!this.canStart()) {
      this.actionMessage = 'A OS deve estar aguardando início e ter um mecânico atribuído.';
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

  private setErrorMessage(error: unknown, fallback: string): void {
    const httpError = error as HttpErrorResponse;
    this.errorMessage =
      (typeof httpError?.error?.detail === 'string' && httpError.error.detail) ||
      fallback;
  }

  onBillingServiceOrderChanged(updated: ServiceOrder): void {
    this.serviceOrder = updated;
    this.selectedStatus = updated.status;
    this.parent.updateServiceOrderInList(updated);
  }

  onBillingActionMessage(message: string): void {
    this.actionMessage = message;
  }
}
