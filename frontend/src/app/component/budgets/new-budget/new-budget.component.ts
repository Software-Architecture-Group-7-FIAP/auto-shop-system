import { Component } from '@angular/core';
import { BudgetService } from '../../../service/budget.service';

@Component({
  selector: 'app-new-budget',
  templateUrl: './new-budget.component.html',
  styleUrls: ['./new-budget.component.css'],
})
export class NewBudgetComponent {
  constructor(private budgetService: BudgetService) {}

  saveBudget(data: { customer_id: string; vehicle_id: string }): void {
    const body = {
      customer_id: Number(data.customer_id),
      vehicle_id: Number(data.vehicle_id),
    };
    this.budgetService.create(body).subscribe(() => {
      window.location.reload();
    });
  }
}
