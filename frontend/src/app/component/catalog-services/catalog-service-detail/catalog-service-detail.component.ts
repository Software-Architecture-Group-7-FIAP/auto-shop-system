import { Component, Input, OnChanges } from '@angular/core';
import { CatalogService, Product } from '../../../model/models';
import { CatalogServiceService } from '../../../service/catalog-service.service';
import { ProductService } from '../../../service/product.service';
import { CatalogServicesComponent } from '../catalog-services.component';

@Component({
  selector: 'app-catalog-service-detail',
  templateUrl: './catalog-service-detail.component.html',
  styleUrls: ['./catalog-service-detail.component.css'],
})
export class CatalogServiceDetailComponent implements OnChanges {
  @Input() catalogServiceId!: number;

  catalogService: CatalogService | undefined;
  products: Product[] = [];
  selectedProductId = 0;
  productQuantity = 1;
  productMessage = '';
  productError = '';
  isCatalogServiceChanged = false;

  constructor(
    private catalogServiceService: CatalogServiceService,
    private productService: ProductService,
    private parent: CatalogServicesComponent
  ) {}

  ngOnChanges(): void {
    if (this.catalogServiceId) {
      this.isCatalogServiceChanged = false;
      this.resetProductFormState();
      this.loadCatalogService();
      this.loadProducts();
    }
  }

  loadCatalogService(): void {
    this.catalogServiceService.getById(this.catalogServiceId).subscribe((data) => {
      this.catalogService = data;
      this.isCatalogServiceChanged = false;
    });
  }

  loadProducts(): void {
    this.productService.getAll().subscribe((data) => {
      this.products = data.sort((a, b) => a.name.localeCompare(b.name));
      if (!this.selectedProductId && this.products.length) {
        this.selectedProductId = this.products[0].id;
      }
    });
  }

  catalogServiceChanged(): void {
    this.isCatalogServiceChanged = true;
  }

  updateCatalogService(): void {
    if (!this.catalogService) {
      return;
    }
    const body = {
      name: this.catalogService.name,
      description: this.catalogService.description,
      base_price: this.catalogService.base_price,
      estimated_hours: this.catalogService.estimated_hours,
    };
    this.catalogServiceService.update(this.catalogServiceId, body).subscribe((updated) => {
      this.catalogService = updated;
      this.isCatalogServiceChanged = false;
      this.parent.updateCatalogServiceInList(updated);
    });
  }

  addProductLine(): void {
    this.productMessage = '';
    this.productError = '';
    if (!this.selectedProductId || this.productQuantity < 1) {
      this.productError = 'Selecione um produto e informe quantidade maior que zero.';
      return;
    }

    this.catalogServiceService
      .addProductLine(this.catalogServiceId, this.selectedProductId, this.productQuantity)
      .subscribe({
        next: () => {
          this.productQuantity = 1;
          this.productMessage = this.currentSelectedProductLine()
            ? 'Quantidade atualizada.'
            : 'Produto vinculado ao serviço.';
          this.reloadCatalogService();
        },
        error: () => {
          this.productError = 'Não foi possível vincular o produto.';
        },
      });
  }

  removeProductLine(lineId: number): void {
    this.productMessage = '';
    this.productError = '';
    this.catalogServiceService.removeProductLine(this.catalogServiceId, lineId).subscribe({
      next: () => {
        this.productMessage = 'Produto removido da composição.';
        this.reloadCatalogService();
      },
      error: () => {
        this.productError = 'Não foi possível remover o produto.';
      },
    });
  }

  productLabel(productId: number): string {
    const product = this.products.find((item) => item.id === productId);
    if (!product) {
      return `Produto #${productId}`;
    }
    return `${product.sku} — ${product.name}`;
  }

  productPrice(productId: number): number | null {
    return this.products.find((item) => item.id === productId)?.unit_price ?? null;
  }

  currentSelectedQuantity(): number | null {
    return this.currentSelectedProductLine()?.quantity ?? null;
  }

  productActionLabel(): string {
    return this.currentSelectedProductLine() ? 'Adicionar quantidade' : 'Vincular produto';
  }

  private currentSelectedProductLine() {
    return this.catalogService?.product_lines.find(
      (line) => line.product_id === this.selectedProductId
    );
  }

  private reloadCatalogService(): void {
    this.catalogServiceService.getById(this.catalogServiceId).subscribe((data) => {
      this.catalogService = data;
      this.parent.updateCatalogServiceInList(data);
    });
  }

  private resetProductFormState(): void {
    this.productQuantity = 1;
    this.productMessage = '';
    this.productError = '';
  }
}
