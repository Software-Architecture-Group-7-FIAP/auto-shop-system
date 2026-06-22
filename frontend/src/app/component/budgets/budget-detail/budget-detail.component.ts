import { Component, Input, OnChanges } from '@angular/core';
import {
  AvailabilityItem,
  Budget,
  BudgetProductLine,
  BudgetServiceLine,
  CatalogService,
  Product,
} from '../../../model/models';
import { BudgetService } from '../../../service/budget.service';
import { CatalogServiceService } from '../../../service/catalog-service.service';
import { ProductService } from '../../../service/product.service';
import { BudgetsComponent } from '../budgets.component';

@Component({
  selector: 'app-budget-detail',
  templateUrl: './budget-detail.component.html',
  styleUrls: ['./budget-detail.component.css'],
})
export class BudgetDetailComponent implements OnChanges {
  @Input() budgetId!: number;

  budget: Budget | undefined;
  products: Product[] = [];
  catalogServices: CatalogService[] = [];
  productLines: BudgetProductLine[] = [];
  serviceLines: BudgetServiceLine[] = [];
  serviceId = 0;
  serviceQuantity = 1;
  productId = 0;
  productQuantity = 1;
  availabilityItems: AvailabilityItem[] = [];

  constructor(
    private budgetService: BudgetService,
    private productService: ProductService,
    private catalogService: CatalogServiceService,
    private parent: BudgetsComponent
  ) {}

  ngOnChanges(): void {
    if (this.budgetId) {
      this.availabilityItems = [];
      this.loadBudget();
      this.loadProducts();
      this.loadCatalogServices();
      this.loadProductLines();
      this.loadServiceLines();
    }
  }

  loadBudget(): void {
    this.budgetService.getById(this.budgetId).subscribe((data) => {
      this.budget = data;
    });
  }

  loadProducts(): void {
    this.productService.getAll().subscribe((products) => {
      this.products = products;
    });
  }

  loadCatalogServices(): void {
    this.catalogService.getAll().subscribe((services) => {
      this.catalogServices = services;
    });
  }

  loadProductLines(): void {
    this.budgetService.listProductLines(this.budgetId).subscribe((lines) => {
      this.productLines = lines;
    });
  }

  loadServiceLines(): void {
    this.budgetService.listServiceLines(this.budgetId).subscribe((lines) => {
      this.serviceLines = lines;
    });
  }

  addServiceLine(): void {
    this.budgetService
      .addServiceLine(this.budgetId, this.serviceId, this.serviceQuantity)
      .subscribe(() => {
        this.reloadBudget();
      });
  }

  removeServiceLine(serviceLineId: number): void {
    this.budgetService
      .removeServiceLine(this.budgetId, serviceLineId)
      .subscribe(() => {
        this.reloadBudget();
      });
  }

  addProductLine(): void {
    this.budgetService
      .addProductLine(this.budgetId, this.productId, this.productQuantity)
      .subscribe(() => {
        this.reloadBudget();
      });
  }

  removeProductLine(productId: number): void {
    this.budgetService
      .removeProductLine(this.budgetId, productId)
      .subscribe(() => {
        this.reloadBudget();
      });
  }

  checkAvailability(): void {
    this.budgetService.checkAvailability(this.budgetId).subscribe((items) => {
      this.availabilityItems = items;
    });
  }

  sendEmail(): void {
    this.budgetService.sendEmail(this.budgetId).subscribe((updated) => {
      this.budget = updated;
      this.parent.updateBudgetInList(updated);
    });
  }

  private reloadBudget(): void {
    this.budgetService.getById(this.budgetId).subscribe((data) => {
      this.budget = data;
      this.parent.updateBudgetInList(data);
    });

    this.loadProductLines();
    this.loadServiceLines();
  }
}