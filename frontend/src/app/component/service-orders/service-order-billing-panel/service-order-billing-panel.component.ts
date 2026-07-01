import { Component, EventEmitter, Input, OnChanges, Output } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Invoice, InvoiceStatus, ServiceOrder, ServiceOrderStatus } from '../../../model/models';
import { ServiceOrderService } from '../../../service/service-order.service';

@Component({
  selector: 'app-service-order-billing-panel',
  templateUrl: './service-order-billing-panel.component.html',
  styleUrls: ['./service-order-billing-panel.component.css'],
})
export class ServiceOrderBillingPanelComponent implements OnChanges {
  @Input() serviceOrderId!: number;
  @Input() serviceOrder: ServiceOrder | undefined;
  @Output() serviceOrderChanged = new EventEmitter<ServiceOrder>();
  @Output() actionMessage = new EventEmitter<string>();

  invoice: Invoice | null = null;
  errorMessage = '';
  isCreatingInvoice = false;
  isPayingInvoice = false;
  private invoiceKnownAbsent = false;
  readonly invoiceStatus = InvoiceStatus;

  constructor(private serviceOrderService: ServiceOrderService) {}

  ngOnChanges(): void {
    this.errorMessage = '';
    this.invoice = null;
    this.invoiceKnownAbsent = false;
    this.loadInvoice();
  }

  shouldShow(): boolean {
    return Boolean(
      this.serviceOrder &&
        [ServiceOrderStatus.FINALIZADA, ServiceOrderStatus.ENTREGUE].includes(
          this.serviceOrder.status
        )
    );
  }

  loadInvoice(): void {
    if (!this.shouldShow()) {
      this.invoice = null;
      return;
    }
    if (this.invoiceKnownAbsent && !this.invoice) {
      return;
    }
    this.serviceOrderService.getInvoice(this.serviceOrderId).subscribe({
      next: (invoice) => {
        this.invoice = invoice;
        this.invoiceKnownAbsent = false;
      },
      error: (error: HttpErrorResponse) => {
        this.invoice = null;
        if (error.status === 404) {
          this.invoiceKnownAbsent = true;
        }
      },
    });
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
        this.invoiceKnownAbsent = false;
        this.actionMessage.emit(`Fatura #${invoice.id} criada — R$ ${invoice.amount.toFixed(2)}`);
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
        this.serviceOrderService.getById(this.serviceOrderId).subscribe((updated) => {
          this.serviceOrderChanged.emit(updated);
          this.actionMessage.emit('Pagamento registrado. OS entregue.');
        });
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

  private setErrorMessage(error: unknown, fallback: string): void {
    const httpError = error as HttpErrorResponse;
    this.errorMessage =
      (typeof httpError?.error?.detail === 'string' && httpError.error.detail) || fallback;
  }
}
