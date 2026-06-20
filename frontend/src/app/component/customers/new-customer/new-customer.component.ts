import { Component } from '@angular/core';
import { CnpjValidation } from '../../../model/models';
import { CustomerService } from '../../../service/customer.service';

@Component({
  selector: 'app-new-customer',
  templateUrl: './new-customer.component.html',
  styleUrls: ['./new-customer.component.css'],
})
export class NewCustomerComponent {
  cnpjValidation: CnpjValidation | null = null;

  constructor(private customerService: CustomerService) {}

  looksLikeCnpj(value: string): boolean {
    return value.replace(/\D/g, '').length === 14;
  }

  validateCnpj(document: string): void {
    const cnpj = document.replace(/\D/g, '');
    this.customerService.validateCnpj(cnpj).subscribe((result) => {
      this.cnpjValidation = result;
    });
  }

  saveCustomer(data: {
    name: string;
    document: string;
    email: string;
    phone: string;
    address: string;
  }): void {
    const body = {
      name: data.name.trim(),
      document: data.document.trim(),
      email: data.email.trim(),
      phone: data.phone?.trim() || null,
      address: data.address.trim(),
    };
    this.customerService.create(body).subscribe(() => {
      window.location.reload();
    });
  }
}
