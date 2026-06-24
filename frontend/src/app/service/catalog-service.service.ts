import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CatalogService, ServiceProductLine } from '../model/models';

@Injectable({ providedIn: 'root' })
export class CatalogServiceService {
  private url = 'api/v1/admin/services';
  private httpOptions = {
    headers: new HttpHeaders({ 'Content-Type': 'application/json' }),
  };

  constructor(private http: HttpClient) {}

  getAll(): Observable<CatalogService[]> {
    return this.http.get<CatalogService[]>(this.url);
  }

  getById(id: number): Observable<CatalogService> {
    return this.http.get<CatalogService>(`${this.url}/${id}`);
  }

  create(body: object): Observable<CatalogService> {
    return this.http.post<CatalogService>(this.url, body, this.httpOptions);
  }

  update(id: number, body: object): Observable<CatalogService> {
    return this.http.put<CatalogService>(`${this.url}/${id}`, body, this.httpOptions);
  }

  addProductLine(
    serviceId: number,
    productId: number,
    quantity: number
  ): Observable<ServiceProductLine> {
    return this.http.post<ServiceProductLine>(
      `${this.url}/${serviceId}/product-lines`,
      { product_id: productId, quantity },
      this.httpOptions
    );
  }

  removeProductLine(serviceId: number, lineId: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${serviceId}/product-lines/${lineId}`);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}`);
  }
}
