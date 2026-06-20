import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Vehicle } from '../model/models';

@Injectable({ providedIn: 'root' })
export class VehicleService {
  private url = 'api/v1/admin/vehicles';
  private httpOptions = {
    headers: new HttpHeaders({ 'Content-Type': 'application/json' }),
  };

  constructor(private http: HttpClient) {}

  getAll(): Observable<Vehicle[]> {
    return this.http.get<Vehicle[]>(this.url);
  }

  getById(id: number): Observable<Vehicle> {
    return this.http.get<Vehicle>(`${this.url}/${id}`);
  }

  create(body: object): Observable<Vehicle> {
    return this.http.post<Vehicle>(this.url, body, this.httpOptions);
  }

  update(id: number, body: object): Observable<Vehicle> {
    return this.http.put<Vehicle>(`${this.url}/${id}`, body, this.httpOptions);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}`);
  }
}
