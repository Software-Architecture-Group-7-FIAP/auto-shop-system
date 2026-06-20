import { Component, Input, OnChanges } from '@angular/core';
import { Supplier } from '../../../model/models';
import { SupplierService } from '../../../service/supplier.service';
import { SuppliersComponent } from '../suppliers.component';

@Component({
  selector: 'app-supplier-detail',
  templateUrl: './supplier-detail.component.html',
  styleUrls: ['./supplier-detail.component.css'],
})
export class SupplierDetailComponent implements OnChanges {
  @Input() supplierId!: number;

  supplier: Supplier | undefined;
  isSupplierChanged = false;

  constructor(
    private supplierService: SupplierService,
    private parent: SuppliersComponent
  ) {}

  ngOnChanges(): void {
    if (this.supplierId) {
      this.isSupplierChanged = false;
      this.loadSupplier();
    }
  }

  loadSupplier(): void {
    this.supplierService.getById(this.supplierId).subscribe((data) => {
      this.supplier = data;
      this.isSupplierChanged = false;
    });
  }

  supplierChanged(): void {
    this.isSupplierChanged = true;
  }

  updateSupplier(): void {
    if (!this.supplier) {
      return;
    }
    const body = {
      name: this.supplier.name,
      email: this.supplier.email,
      phone: this.supplier.phone,
    };
    this.supplierService.update(this.supplierId, body).subscribe((updated) => {
      this.supplier = updated;
      this.isSupplierChanged = false;
      this.parent.updateSupplierInList(updated);
    });
  }
}
