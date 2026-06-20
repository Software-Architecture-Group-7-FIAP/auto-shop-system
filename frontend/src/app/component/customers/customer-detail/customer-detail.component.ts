import { Component, Input, OnChanges } from '@angular/core';
import { CnpjValidation, Customer } from '../../../model/models';
import { CustomerService } from '../../../service/customer.service';
import { CustomersComponent } from '../customers.component';

@Component({
  selector: 'app-customer-detail',
  templateUrl: './customer-detail.component.html',
  styleUrls: ['./customer-detail.component.css'],
})
export class CustomerDetailComponent implements OnChanges {
  @Input() customerId!: number;

  customer: Customer | undefined;
  isCustomerChanged = false;
  newDocument = '';
  cnpjValidation: CnpjValidation | null = null;

  constructor(
    private customerService: CustomerService,
    private parent: CustomersComponent
  ) {}

  ngOnChanges(): void {
    if (this.customerId) {
      this.isCustomerChanged = false;
      this.newDocument = '';
      this.cnpjValidation = null;
      this.loadCustomer();
    }
  }

  loadCustomer(): void {
    this.customerService.getById(this.customerId).subscribe((data) => {
      this.customer = data;
      this.isCustomerChanged = false;
    });
  }

  customerChanged(): void {
    this.isCustomerChanged = true;
  }

  updateCustomer(): void {
    if (!this.customer) {
      return;
    }
    const body = {
      name: this.customer.name,
      email: this.customer.email,
      phone: this.customer.phone,
      address: this.customer.address,
    };
    this.customerService.update(this.customerId, body).subscribe((updated) => {
      this.customer = updated;
      this.isCustomerChanged = false;
      this.parent.updateCustomerInList(updated);
    });
  }

  looksLikeCnpj(value: string): boolean {
    return value.replace(/\D/g, '').length === 14;
  }

  validateCnpj(document: string): void {
    const cnpj = document.replace(/\D/g, '');
    this.customerService.validateCnpj(cnpj).subscribe((result) => {
      this.cnpjValidation = result;
    });
  }

  addDocument(): void {
    const document = this.newDocument.trim();
    if (!document) {
      return;
    }
    this.customerService.addDocument(this.customerId, document).subscribe((updated) => {
      this.customer = updated;
      this.newDocument = '';
      this.parent.updateCustomerInList(updated);
    });
  }
}
