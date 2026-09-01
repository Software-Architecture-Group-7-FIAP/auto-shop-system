import { of, throwError } from 'rxjs';
import { Budget, BudgetStatus } from '../../../model/models';
import { BudgetDetailComponent } from './budget-detail.component';

describe('BudgetDetailComponent email flow', () => {
  const makeBudget = (status: BudgetStatus): Budget => ({
    id: 1,
    customer_id: 1,
    vehicle_id: 1,
    status,
    total_price: 295.9,
    estimated_delivery: null,
    created_at: new Date().toISOString(),
    revision_number: 1,
    supersedes_budget_id: null,
  });

  it('reloads the budget after sending the approval email', () => {
    const persistedBudget = makeBudget(BudgetStatus.SENT);
    const budgetService = {
      sendEmail: jasmine.createSpy('sendEmail').and.returnValue(
        of(makeBudget(BudgetStatus.DRAFT))
      ),
      getById: jasmine.createSpy('getById').and.returnValue(of(persistedBudget)),
      listProductLines: jasmine.createSpy('listProductLines').and.returnValue(of([])),
      listServiceLines: jasmine.createSpy('listServiceLines').and.returnValue(of([])),
    };
    const parent = {
      updateBudgetInList: jasmine.createSpy('updateBudgetInList'),
    };
    const component = new BudgetDetailComponent(
      budgetService as any,
      {} as any,
      {} as any,
      parent as any
    );
    component.budgetId = 1;

    component.sendEmail();

    expect(budgetService.sendEmail).toHaveBeenCalledWith(1);
    expect(budgetService.getById).toHaveBeenCalledWith(1);
    expect(component.budget).toEqual(persistedBudget);
    expect(parent.updateBudgetInList).toHaveBeenCalledWith(persistedBudget);
    expect(component.actionMessage).toBe('E-mail do orçamento enviado com sucesso.');
    expect(component.isSendingEmail).toBeFalse();
  });

  it('shows a useful error when sending the email fails', () => {
    const budgetService = {
      sendEmail: jasmine.createSpy('sendEmail').and.returnValue(
        throwError(() => ({ error: { detail: 'SMTP indisponível' } }))
      ),
    };
    const component = new BudgetDetailComponent(
      budgetService as any,
      {} as any,
      {} as any,
      {} as any
    );
    component.budgetId = 1;

    component.sendEmail();

    expect(component.errorMessage).toBe('SMTP indisponível');
    expect(component.isSendingEmail).toBeFalse();
  });
});
