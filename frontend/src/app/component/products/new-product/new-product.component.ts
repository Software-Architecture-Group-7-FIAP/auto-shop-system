import { Component } from '@angular/core';
import { ProductService } from '../../../service/product.service';

@Component({
  selector: 'app-new-product',
  templateUrl: './new-product.component.html',
  styleUrls: ['./new-product.component.css'],
})
export class NewProductComponent {
  constructor(private productService: ProductService) {}

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
      supplier_id: data.supplier_id ? Number(data.supplier_id) : null,
    };
    this.productService.create(body).subscribe(() => {
      window.location.reload();
    });
  }
}
