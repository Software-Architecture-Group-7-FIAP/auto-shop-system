import { Component, OnInit } from '@angular/core';
import { Supplier } from '../../model/models';
import { SupplierService } from '../../service/supplier.service';

@Component({
  selector: 'app-suppliers',
  templateUrl: './suppliers.component.html',
  styleUrls: ['./suppliers.component.css'],
})
export class SuppliersComponent implements OnInit {
  suppliers: Supplier[] = [];
  selectedSupplierId: number | undefined;
  creatingNewSupplier = false;

  constructor(private supplierService: SupplierService) {}

  ngOnInit(): void {
    this.supplierService.getAll().subscribe((data) => {
      this.suppliers = data.sort((a, b) => a.id - b.id);
    });
  }

  selectSupplier(id: number): void {
    this.selectedSupplierId = id;
    this.creatingNewSupplier = false;
  }

  toCreatingMode = (): void => {
    this.selectedSupplierId = undefined;
    this.creatingNewSupplier = true;
  };

  updateSupplierInList(supplier: Supplier): void {
    const index = this.suppliers.findIndex((s) => s.id === supplier.id);
    if (index >= 0) {
      this.suppliers[index] = supplier;
    }
  }
}
