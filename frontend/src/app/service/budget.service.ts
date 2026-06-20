import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AvailabilityItem, Budget } from '../model/models';

@Injectable({ providedIn: 'root' })
export class BudgetService {
  private url = 'api/v1/admin/budgets';
  private httpOptions = {
    headers: new HttpHeaders({ 'Content-Type': 'application/json' }),
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

  addServiceLine(budgetId: number, serviceId: number, quantity: number): Observable<unknown> {
    return this.http.post(
      `${this.url}/${budgetId}/service-lines`,
      { service_id: serviceId, quantity },
      this.httpOptions
    );
  }

  addProductLine(budgetId: number, productId: number, quantity: number): Observable<unknown> {
    return this.http.post(
      `${this.url}/${budgetId}/product-lines`,
      { product_id: productId, quantity },
      this.httpOptions
    );
  }

  checkAvailability(budgetId: number): Observable<AvailabilityItem[]> {
    return this.http.get<AvailabilityItem[]>(`${this.url}/${budgetId}/availability`);
  }

  sendEmail(budgetId: number): Observable<Budget> {
    return this.http.post<Budget>(`${this.url}/${budgetId}/send-email`, {}, this.httpOptions);
  }
}
