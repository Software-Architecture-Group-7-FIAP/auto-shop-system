import { Component, Input, OnChanges } from '@angular/core';
import { AvailabilityItem, Budget } from '../../../model/models';
import { BudgetService } from '../../../service/budget.service';
import { BudgetsComponent } from '../budgets.component';

@Component({
  selector: 'app-budget-detail',
  templateUrl: './budget-detail.component.html',
  styleUrls: ['./budget-detail.component.css'],
})
export class BudgetDetailComponent implements OnChanges {
  @Input() budgetId!: number;

  budget: Budget | undefined;
  serviceId = 0;
  serviceQuantity = 1;
  productId = 0;
  productQuantity = 1;
  availabilityItems: AvailabilityItem[] = [];

  constructor(
    private budgetService: BudgetService,
    private parent: BudgetsComponent
  ) {}

  ngOnChanges(): void {
    if (this.budgetId) {
      this.availabilityItems = [];
      this.loadBudget();
    }
  }

  loadBudget(): void {
    this.budgetService.getById(this.budgetId).subscribe((data) => {
      this.budget = data;
    });
  }

  addServiceLine(): void {
    this.budgetService
      .addServiceLine(this.budgetId, this.serviceId, this.serviceQuantity)
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
  }
}
