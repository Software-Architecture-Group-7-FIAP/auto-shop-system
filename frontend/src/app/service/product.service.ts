import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Product } from '../model/models';

@Injectable({ providedIn: 'root' })
export class ProductService {
  private url = 'api/v1/admin/products';
  private httpOptions = {
    headers: new HttpHeaders({ 'Content-Type': 'application/json' }),
  };

  constructor(private http: HttpClient) {}

  getAll(): Observable<Product[]> {
    return this.http.get<Product[]>(this.url);
  }

  getById(id: number): Observable<Product> {
    return this.http.get<Product>(`${this.url}/${id}`);
  }

  create(body: object): Observable<Product> {
    return this.http.post<Product>(this.url, body, this.httpOptions);
  }

  update(id: number, body: object): Observable<Product> {
    return this.http.put<Product>(`${this.url}/${id}`, body, this.httpOptions);
  }

  updateStock(id: number, quantity: number): Observable<Product> {
    return this.http.patch<Product>(`${this.url}/${id}/stock`, { quantity }, this.httpOptions);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}`);
  }
}
