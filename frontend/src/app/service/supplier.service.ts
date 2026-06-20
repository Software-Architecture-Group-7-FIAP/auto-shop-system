import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Supplier } from '../model/models';

@Injectable({ providedIn: 'root' })
export class SupplierService {
  private url = 'api/v1/admin/suppliers';
  private httpOptions = {
    headers: new HttpHeaders({ 'Content-Type': 'application/json' }),
  };

  constructor(private http: HttpClient) {}

  getAll(): Observable<Supplier[]> {
    return this.http.get<Supplier[]>(this.url);
  }

  getById(id: number): Observable<Supplier> {
    return this.http.get<Supplier>(`${this.url}/${id}`);
  }

  create(body: object): Observable<Supplier> {
    return this.http.post<Supplier>(this.url, body, this.httpOptions);
  }

  update(id: number, body: object): Observable<Supplier> {
    return this.http.put<Supplier>(`${this.url}/${id}`, body, this.httpOptions);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}`);
  }
}
