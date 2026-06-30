import { Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  AverageExecutionTime,
  Invoice,
  MessageResponse,
  Priority,
  ServiceOrder,
  ServiceOrderPublic,
  ServiceOrderUpdate,
} from '../model/models';
import { SKIP_GLOBAL_ERROR_ALERT } from './http-error.interceptor';

@Injectable({ providedIn: 'root' })
export class ServiceOrderService {
  private url = 'api/v1/admin/service-orders';
  private httpOptions = {
    headers: new HttpHeaders({ 'Content-Type': 'application/json' }),
  };

  constructor(private http: HttpClient) {}

  getAll(status?: string): Observable<ServiceOrder[]> {
    const params = status ? `?status=${encodeURIComponent(status)}` : '';
    return this.http.get<ServiceOrder[]>(`${this.url}${params}`);
  }

  getById(id: number): Observable<ServiceOrder> {
    return this.http.get<ServiceOrder>(`${this.url}/${id}`);
  }

  assignMechanic(id: number, mechanicName: string): Observable<ServiceOrder> {
    return this.http.patch<ServiceOrder>(
      `${this.url}/${id}/assign-mechanic`,
      { mechanic_name: mechanicName },
      this.httpOptions
    );
  }

  update(id: number, payload: ServiceOrderUpdate): Observable<ServiceOrder> {
    return this.http.put<ServiceOrder>(`${this.url}/${id}`, payload, this.httpOptions);
  }

  setPriority(id: number, priority: Priority): Observable<ServiceOrder> {
    return this.http.patch<ServiceOrder>(
      `${this.url}/${id}/priority`,
      { priority },
      this.httpOptions
    );
  }

  sendEmail(id: number): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(`${this.url}/${id}/send-email`, {}, this.httpOptions);
  }

  trackPublic(token: string): Observable<ServiceOrderPublic> {
    return this.http.get<ServiceOrderPublic>(
      `api/v1/public/service-orders/track/${encodeURIComponent(token)}`,
      {
        context: new HttpContext().set(SKIP_GLOBAL_ERROR_ALERT, true),
      }
    );
  }

  getAverageExecutionTime(): Observable<AverageExecutionTime> {
    return this.http.get<AverageExecutionTime>(`${this.url}/metrics/average-execution-time`);
  }

  createInvoice(serviceOrderId: number): Observable<Invoice> {
    return this.http.post<Invoice>(
      `api/v1/admin/service-orders/${serviceOrderId}/invoice`,
      {},
      this.httpOptions
    );
  }

  getInvoice(serviceOrderId: number): Observable<Invoice> {
    return this.http.get<Invoice>(
      `api/v1/admin/service-orders/${serviceOrderId}/invoice`,
      {
        context: new HttpContext().set(SKIP_GLOBAL_ERROR_ALERT, true),
      }
    );
  }

  startServiceOrder(serviceOrderId: number): Observable<ServiceOrder> {
    return this.http.patch<ServiceOrder>(
      `${this.url}/${serviceOrderId}/start`,
      {},
      this.httpOptions
    );
  }

  finishServiceOrder(serviceOrderId: number): Observable<ServiceOrder> {
    return this.http.patch<ServiceOrder>(
      `${this.url}/${serviceOrderId}/finish`,
      {},
      this.httpOptions
    );
  }

  payInvoice(invoiceId: number): Observable<Invoice> {
    return this.http.patch<Invoice>(
      `api/v1/admin/invoices/${invoiceId}/pay`,
      {},
      this.httpOptions
    );
  }

  deliver(serviceOrderId: number): Observable<ServiceOrder> {
    return this.http.patch<ServiceOrder>(
      `api/v1/admin/service-orders/${serviceOrderId}/deliver`,
      {},
      this.httpOptions
    );
  }
}
