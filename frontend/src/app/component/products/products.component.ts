import { Component, OnInit } from '@angular/core';
import { Product } from '../../model/models';
import { ProductService } from '../../service/product.service';

@Component({
  selector: 'app-products',
  templateUrl: './products.component.html',
  styleUrls: ['./products.component.css'],
})
export class ProductsComponent implements OnInit {
  products: Product[] = [];
  selectedProductId: number | undefined;
  creatingNewProduct = false;

  constructor(private productService: ProductService) {}

  ngOnInit(): void {
    this.productService.getAll().subscribe((data) => {
      this.products = data.sort((a, b) => a.id - b.id);
    });
  }

  selectProduct(id: number): void {
    this.selectedProductId = id;
    this.creatingNewProduct = false;
  }

  toCreatingMode = (): void => {
    this.selectedProductId = undefined;
    this.creatingNewProduct = true;
  };

  updateProductInList(product: Product): void {
    const index = this.products.findIndex((p) => p.id === product.id);
    if (index >= 0) {
      this.products[index] = product;
    }
  }
}
