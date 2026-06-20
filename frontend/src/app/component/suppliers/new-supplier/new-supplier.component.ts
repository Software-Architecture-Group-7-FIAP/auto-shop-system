import { Component } from '@angular/core';
import { SupplierService } from '../../../service/supplier.service';

@Component({
  selector: 'app-new-supplier',
  templateUrl: './new-supplier.component.html',
  styleUrls: ['./new-supplier.component.css'],
})
export class NewSupplierComponent {
  constructor(private supplierService: SupplierService) {}

  saveSupplier(data: {
    name: string;
    document: string;
    email: string;
    phone: string;
  }): void {
    const body = {
      name: data.name.trim(),
      document: data.document.trim(),
      email: data.email.trim(),
      phone: data.phone?.trim() || null,
    };
    this.supplierService.create(body).subscribe(() => {
      window.location.reload();
    });
  }
}
