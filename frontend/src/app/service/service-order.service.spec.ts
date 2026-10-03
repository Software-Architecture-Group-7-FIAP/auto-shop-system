import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ServiceOrderService } from './service-order.service';

describe('ServiceOrderService listing', () => {
  let service: ServiceOrderService;
  let httpTestingController: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    service = TestBed.inject(ServiceOrderService);
    httpTestingController = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpTestingController.verify());

  it('requests the operational priority ordering by default', () => {
    service.getAll().subscribe();

    const request = httpTestingController.expectOne(
      (candidate) => candidate.url === 'api/v1/admin/service-orders',
    );

    expect(request.request.params.get('order_by')).toBe('priority');
    request.flush({ items: [], page: 1, page_size: 20, total: 0, total_pages: 0 });
  });
});
