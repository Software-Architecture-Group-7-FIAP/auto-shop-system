import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { BudgetService } from '../../service/budget.service';

type BudgetApprovalAction = 'approve' | 'reject';

@Component({
  selector: 'app-budget-approval',
  templateUrl: './budget-approval.component.html',
  styleUrls: ['./budget-approval.component.css'],
})
export class BudgetApprovalComponent implements OnInit {
  token = '';
  selectedAction: BudgetApprovalAction | null = null;
  isSubmitting = false;
  message = '';
  isSuccess = false;

  constructor(
    private route: ActivatedRoute,
    private budgetService: BudgetService
  ) {}

  ngOnInit(): void {
    this.token = this.route.snapshot.fragment || '';
    if (this.token) {
      window.history.replaceState({}, document.title, window.location.pathname + window.location.search);
    }
    const action = this.route.snapshot.queryParamMap.get('action');
    if (action === 'approve' || action === 'reject') {
      this.selectedAction = action;
    }
    if (!this.token) {
      this.message = 'Link de orçamento inválido.';
    }
  }

  selectAction(action: BudgetApprovalAction): void {
    this.selectedAction = action;
    this.message = '';
    this.isSuccess = false;
  }

  submit(): void {
    if (!this.token || !this.selectedAction || this.isSubmitting) {
      return;
    }

    this.isSubmitting = true;
    this.message = '';
    this.isSuccess = false;

    const request = this.selectedAction === 'approve'
      ? this.budgetService.approvePublicBudget(this.token)
      : this.budgetService.rejectPublicBudget(this.token);

    request.subscribe({
      next: (response) => {
        this.message = response.message;
        this.isSuccess = true;
      },
      complete: () => {
        this.isSubmitting = false;
      },
      error: (error) => {
        this.message = error.error?.detail || 'Não foi possível processar o orçamento.';
        this.isSubmitting = false;
      },
    });
  }

  actionLabel(): string {
    if (this.selectedAction === 'approve') {
      return 'Confirmar aprovação';
    }
    if (this.selectedAction === 'reject') {
      return 'Confirmar recusa';
    }
    return 'Selecione uma ação';
  }
}
