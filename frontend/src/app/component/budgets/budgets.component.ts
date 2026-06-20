import { Component, OnInit } from '@angular/core';
import { Budget } from '../../model/models';
import { BudgetService } from '../../service/budget.service';

@Component({
  selector: 'app-budgets',
  templateUrl: './budgets.component.html',
  styleUrls: ['./budgets.component.css'],
})
export class BudgetsComponent implements OnInit {
  budgets: Budget[] = [];
  selectedBudgetId: number | undefined;
  creatingNewBudget = false;

  constructor(private budgetService: BudgetService) {}

  ngOnInit(): void {
    this.budgetService.getAll().subscribe((data) => {
      this.budgets = data.sort((a, b) => a.id - b.id);
    });
  }

  selectBudget(id: number): void {
    this.selectedBudgetId = id;
    this.creatingNewBudget = false;
  }

  toCreatingMode = (): void => {
    this.selectedBudgetId = undefined;
    this.creatingNewBudget = true;
  };

  updateBudgetInList(budget: Budget): void {
    const index = this.budgets.findIndex((b) => b.id === budget.id);
    if (index >= 0) {
      this.budgets[index] = budget;
    }
  }
}
