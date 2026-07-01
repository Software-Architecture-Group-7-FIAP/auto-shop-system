import { Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  AvailabilityItem,
  Budget,
  BudgetProductLine,
  BudgetServiceLine,
  MessageResponse,
} from '../model/models';
import { SKIP_GLOBAL_ERROR_ALERT } from './http-error.interceptor';

@Injectable({ providedIn: 'root' })
export class BudgetService {
  private url = 'api/v1/admin/budgets';

  private httpOptions = {
    headers: new HttpHeaders({
      'Content-Type': 'application/json',
    }),
  };

  constructor(private http: HttpClient) {}

  getAll(): Observable<Budget[]> {
    return this.http.get<Budget[]>(this.url);
  }

  getById(id: number): Observable<Budget> {
    return this.http.get<Budget>(`${this.url}/${id}`);
  }

  create(body: object): Observable<Budget> {
    return this.http.post<Budget>(this.url, body, this.httpOptions);
  }

  addServiceLine(
    budgetId: number,
    serviceId: number,
    quantity: number
  ): Observable<unknown> {
    return this.http.post(
      `${this.url}/${budgetId}/service-lines`,
      { service_id: serviceId, quantity },
      this.httpOptions
    );
  }

  listServiceLines(budgetId: number): Observable<BudgetServiceLine[]> {
    return this.http.get<BudgetServiceLine[]>(
      `${this.url}/${budgetId}/service-lines`
    );
  }

  updateServiceLine(
    budgetId: number,
    lineId: number,
    quantity: number
  ): Observable<BudgetServiceLine> {
    return this.http.put<BudgetServiceLine>(
      `${this.url}/${budgetId}/service-lines/${lineId}`,
      { quantity },
      this.httpOptions
    );
  }

  removeServiceLine(
    budgetId: number,
    lineId: number
  ): Observable<unknown> {
    return this.http.delete(
      `${this.url}/${budgetId}/service-lines/${lineId}`
    );
  }

  addProductLine(
    budgetId: number,
    productId: number,
    quantity: number
  ): Observable<unknown> {
    return this.http.post(
      `${this.url}/${budgetId}/product-lines`,
      { product_id: productId, quantity },
      this.httpOptions
    );
  }

  listProductLines(budgetId: number): Observable<BudgetProductLine[]> {
    return this.http.get<BudgetProductLine[]>(
      `${this.url}/${budgetId}/product-lines`
    );
  }

  updateProductLine(
    budgetId: number,
    lineId: number,
    quantity: number
  ): Observable<BudgetProductLine> {
    return this.http.put<BudgetProductLine>(
      `${this.url}/${budgetId}/product-lines/${lineId}`,
      { quantity },
      this.httpOptions
    );
  }

  removeProductLine(
    budgetId: number,
    lineId: number
  ): Observable<unknown> {
    return this.http.delete(
      `${this.url}/${budgetId}/product-lines/${lineId}`
    );
  }

  checkAvailability(budgetId: number): Observable<AvailabilityItem[]> {
    return this.http.get<AvailabilityItem[]>(
      `${this.url}/${budgetId}/availability`
    );
  }

  sendEmail(budgetId: number): Observable<Budget> {
    return this.http.post<Budget>(
      `${this.url}/${budgetId}/send-email`,
      {},
      this.httpOptions
    );
  }

  approve(budgetId: number): Observable<MessageResponse> {
    return this.http.patch<MessageResponse>(
      `${this.url}/${budgetId}/approve`,
      {},
      this.httpOptions
    );
  }

  approvePublicBudget(token: string): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(
      `api/v1/public/budgets/${encodeURIComponent(token)}/approve`,
      {},
      {
        ...this.httpOptions,
        context: new HttpContext().set(SKIP_GLOBAL_ERROR_ALERT, true),
      }
    );
  }

  rejectPublicBudget(token: string): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(
      `api/v1/public/budgets/${encodeURIComponent(token)}/reject`,
      {},
      {
        ...this.httpOptions,
        context: new HttpContext().set(SKIP_GLOBAL_ERROR_ALERT, true),
      }
    );
  }
}
