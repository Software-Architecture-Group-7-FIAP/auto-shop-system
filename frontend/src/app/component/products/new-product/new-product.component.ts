import { Component, OnInit } from '@angular/core';
import { Supplier } from '../../../model/models';
import { ProductService } from '../../../service/product.service';
import { SupplierService } from '../../../service/supplier.service';

@Component({
  selector: 'app-new-product',
  templateUrl: './new-product.component.html',
  styleUrls: ['./new-product.component.css'],
})
export class NewProductComponent implements OnInit {
  suppliers: Supplier[] = [];
  errorMessage = '';

  constructor(
    private productService: ProductService,
    private supplierService: SupplierService
  ) {}

  ngOnInit(): void {
    this.supplierService.getAll().subscribe((data) => {
      this.suppliers = data.sort((a, b) => a.name.localeCompare(b.name));
    });
  }

  saveProduct(data: {
    name: string;
    sku: string;
    unit_price: string;
    stock_quantity: string;
    description: string;
    supplier_id: string;
  }): void {
    const body = {
      name: data.name.trim(),
      sku: data.sku.trim(),
      unit_price: Number(data.unit_price),
      stock_quantity: Number(data.stock_quantity) || 0,
      description: data.description?.trim() || null,
      supplier_id: Number(data.supplier_id),
    };
    this.errorMessage = '';
    this.productService.create(body).subscribe({
      next: () => {
        window.location.reload();
      },
      error: (error) => {
        this.errorMessage = error?.error?.detail || 'Não foi possível salvar o produto.';
      },
    });
  }
}
