import { Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Vehicle } from '../model/models';
import { SKIP_GLOBAL_ERROR_ALERT } from './http-error.interceptor';

@Injectable({ providedIn: 'root' })
export class VehicleService {
  private url = 'api/v1/admin/vehicles';
  private jsonOptions = {
    headers: new HttpHeaders({ 'Content-Type': 'application/json' }),
    context: new HttpContext().set(SKIP_GLOBAL_ERROR_ALERT, true),
  };

  constructor(private http: HttpClient) {}

  getAll(): Observable<Vehicle[]> {
    return this.http.get<Vehicle[]>(this.url);
  }

  getById(id: number): Observable<Vehicle> {
    return this.http.get<Vehicle>(`${this.url}/${id}`);
  }

  getByCustomer(customerId: number): Observable<Vehicle[]> {
    return this.http.get<Vehicle[]>(
      `api/v1/admin/customers/${customerId}/vehicles`
    );
  }

  create(body: object): Observable<Vehicle> {
    return this.http.post<Vehicle>(this.url, body, this.jsonOptions);
  }

  update(id: number, body: object): Observable<Vehicle> {
    return this.http.put<Vehicle>(`${this.url}/${id}`, body, this.jsonOptions);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}`);
  }
}
