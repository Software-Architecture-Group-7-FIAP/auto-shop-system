import { Component, Input, OnChanges, OnInit } from '@angular/core';
import { Product, Supplier } from '../../../model/models';
import { ProductService } from '../../../service/product.service';
import { SupplierService } from '../../../service/supplier.service';
import { ProductsComponent } from '../products.component';

@Component({
  selector: 'app-product-detail',
  templateUrl: './product-detail.component.html',
  styleUrls: ['./product-detail.component.css'],
})
export class ProductDetailComponent implements OnChanges, OnInit {
  @Input() productId!: number;

  product: Product | undefined;
  suppliers: Supplier[] = [];
  errorMessage = '';
  isProductChanged = false;
  stockQuantity = 0;

  constructor(
    private productService: ProductService,
    private supplierService: SupplierService,
    private parent: ProductsComponent
  ) {}

  ngOnInit(): void {
    this.supplierService.getAll().subscribe((data) => {
      this.suppliers = data.sort((a, b) => a.name.localeCompare(b.name));
    });
  }

  ngOnChanges(): void {
    if (this.productId) {
      this.isProductChanged = false;
      this.loadProduct();
    }
  }

  loadProduct(): void {
    this.productService.getById(this.productId).subscribe((data) => {
      this.product = data;
      this.stockQuantity = data.stock_quantity;
      this.isProductChanged = false;
    });
  }

  productChanged(): void {
    this.isProductChanged = true;
  }

  updateProduct(): void {
    if (!this.product) {
      return;
    }
    const body = {
      name: this.product.name,
      unit_price: this.product.unit_price,
      description: this.product.description,
      supplier_id: this.product.supplier_id,
    };
    this.errorMessage = '';
    this.productService.update(this.productId, body).subscribe({
      next: (updated) => {
        this.product = updated;
        this.stockQuantity = updated.stock_quantity;
        this.isProductChanged = false;
        this.parent.updateProductInList(updated);
      },
      error: (error) => {
        this.errorMessage = error?.error?.detail || 'Não foi possível atualizar o produto.';
      },
    });
  }

  updateStock(): void {
    this.productService.updateStock(this.productId, this.stockQuantity).subscribe((updated) => {
      this.product = updated;
      this.stockQuantity = updated.stock_quantity;
      this.parent.updateProductInList(updated);
    });
  }
}
