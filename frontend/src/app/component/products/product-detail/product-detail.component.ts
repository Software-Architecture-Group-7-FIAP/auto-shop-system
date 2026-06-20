import { Component, Input, OnChanges } from '@angular/core';
import { Product } from '../../../model/models';
import { ProductService } from '../../../service/product.service';
import { ProductsComponent } from '../products.component';

@Component({
  selector: 'app-product-detail',
  templateUrl: './product-detail.component.html',
  styleUrls: ['./product-detail.component.css'],
})
export class ProductDetailComponent implements OnChanges {
  @Input() productId!: number;

  product: Product | undefined;
  isProductChanged = false;
  stockQuantity = 0;

  constructor(
    private productService: ProductService,
    private parent: ProductsComponent
  ) {}

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
    this.productService.update(this.productId, body).subscribe((updated) => {
      this.product = updated;
      this.stockQuantity = updated.stock_quantity;
      this.isProductChanged = false;
      this.parent.updateProductInList(updated);
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
