import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  AverageExecutionTime,
  Invoice,
  MessageResponse,
  Priority,
  ServiceOrder,
} from '../model/models';

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
