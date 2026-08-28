import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CnpjValidation, CpfValidation, Customer } from '../model/models';

@Injectable({ providedIn: 'root' })
export class CustomerService {
  private url = 'api/v1/admin/customers';
  private httpOptions = {
    headers: new HttpHeaders({ 'Content-Type': 'application/json' }),
  };

  constructor(private http: HttpClient) {}

  getAll(): Observable<Customer[]> {
    return this.http.get<Customer[]>(this.url);
  }

  getById(id: number): Observable<Customer> {
    return this.http.get<Customer>(`${this.url}/${id}`);
  }

  create(body: object): Observable<Customer> {
    return this.http.post<Customer>(this.url, body, this.httpOptions);
  }

  update(id: number, body: object): Observable<Customer> {
    return this.http.put<Customer>(`${this.url}/${id}`, body, this.httpOptions);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}`);
  }

  validateCnpj(cnpj: string): Observable<CnpjValidation> {
    return this.http.post<CnpjValidation>(`${this.url}/validate-cnpj`, { document: cnpj }, this.httpOptions);
  }

  validateCpf(cpf: string): Observable<CpfValidation> {
    return this.http.post<CpfValidation>(`${this.url}/validate-cpf`, { document: cpf }, this.httpOptions);
  }

  addDocument(id: number, document: string): Observable<Customer> {
    return this.http.post<Customer>(
      `${this.url}/${id}/documents`,
      { document },
      this.httpOptions
    );
  }
}
