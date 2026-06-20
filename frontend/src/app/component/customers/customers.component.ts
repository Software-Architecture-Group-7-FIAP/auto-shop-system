import { Component, OnInit } from '@angular/core';
import { Customer } from '../../model/models';
import { CustomerService } from '../../service/customer.service';

@Component({
  selector: 'app-customers',
  templateUrl: './customers.component.html',
  styleUrls: ['./customers.component.css'],
})
export class CustomersComponent implements OnInit {
  customers: Customer[] = [];
  selectedCustomerId: number | undefined;
  creatingNewCustomer = false;

  constructor(private customerService: CustomerService) {}

  ngOnInit(): void {
    this.customerService.getAll().subscribe((data) => {
      this.customers = data.sort((a, b) => a.id - b.id);
    });
  }

  selectCustomer(id: number): void {
    this.selectedCustomerId = id;
    this.creatingNewCustomer = false;
  }

  toCreatingMode = (): void => {
    this.selectedCustomerId = undefined;
    this.creatingNewCustomer = true;
  };

  updateCustomerInList(customer: Customer): void {
    const index = this.customers.findIndex((c) => c.id === customer.id);
    if (index >= 0) {
      this.customers[index] = customer;
    }
  }
}
