import {
  Priority,
  ServiceOrder,
  ServiceOrderStatus,
} from '../../../model/models';
import { of, throwError } from 'rxjs';
import { ServiceOrderDetailComponent } from './service-order-detail.component';

describe('ServiceOrderDetailComponent start rules', () => {
  const makeComponent = (): ServiceOrderDetailComponent =>
    new ServiceOrderDetailComponent({} as any, {} as any);

  const makeOrder = (status: ServiceOrderStatus, mechanicName: string | null): ServiceOrder => ({
    id: 1,
    budget_id: 1,
    customer_id: 1,
    vehicle_id: 1,
    status,
    priority: Priority.NORMAL,
    mechanic_name: mechanicName,
    total_price: 100,
    started_at: null,
    finished_at: null,
    created_at: new Date().toISOString(),
  });

  it('only enables start while the order is awaiting execution', () => {
    const component = makeComponent();
    component.serviceOrder = makeOrder(ServiceOrderStatus.AGUARDANDO_INICIO, 'João');

    expect(component.canStart()).toBeTrue();
    expect(component.shouldShowStart()).toBeTrue();

    component.serviceOrder = makeOrder(ServiceOrderStatus.AGUARDANDO_APROVACAO, 'João');
    expect(component.canStart()).toBeFalse();
    expect(component.shouldShowStart()).toBeFalse();
  });

  it('requires a mechanic even in the awaiting-start state', () => {
    const component = makeComponent();
    component.serviceOrder = makeOrder(ServiceOrderStatus.AGUARDANDO_INICIO, null);

    expect(component.canStart()).toBeFalse();
    expect(component.shouldShowStart()).toBeTrue();
  });

  it('sends a reason when replacing an assigned mechanic', () => {
    const updated = makeOrder(ServiceOrderStatus.EM_DIAGNOSTICO, 'Maria');
    const service = {
      update: jasmine.createSpy('update').and.returnValue(of(updated)),
    };
    const parent = { updateServiceOrderInList: jasmine.createSpy('updateServiceOrderInList') };
    const component = new ServiceOrderDetailComponent(service as any, parent as any);
    component.serviceOrder = makeOrder(ServiceOrderStatus.EM_DIAGNOSTICO, 'João');
    component.serviceOrderId = 1;
    component.mechanicName = 'Maria';
    component.mechanicChangeReason = 'Redistribuição da equipe';

    component.saveChanges();

    expect(service.update).toHaveBeenCalledWith(1, {
      priority: Priority.NORMAL,
      mechanic_name: 'Maria',
      reason: 'Redistribuição da equipe',
    });
  });

  it('does not submit a mechanic replacement without a reason', () => {
    const service = { update: jasmine.createSpy('update') };
    const component = new ServiceOrderDetailComponent(service as any, {} as any);
    component.serviceOrder = makeOrder(ServiceOrderStatus.EM_DIAGNOSTICO, 'João');
    component.mechanicName = 'Maria';
    component.actionMessage = 'Ordem de serviço atualizada.';

    component.saveChanges();

    expect(service.update).not.toHaveBeenCalled();
    expect(component.errorMessage).toContain('Motivo obrigatório');
    expect(component.actionMessage).toBe('');
  });

  it('shows backend errors when saving the order fails', () => {
    const service = {
      update: jasmine.createSpy('update').and.returnValue(
        throwError(() => ({ error: { detail: 'OS bloqueada' } }))
      ),
    };
    const component = new ServiceOrderDetailComponent(service as any, {} as any);
    component.serviceOrder = makeOrder(ServiceOrderStatus.EM_DIAGNOSTICO, 'João');
    component.mechanicName = 'João';

    component.saveChanges();

    expect(component.errorMessage).toBe('OS bloqueada');
    expect(component.isSaving).toBeFalse();
  });
});
