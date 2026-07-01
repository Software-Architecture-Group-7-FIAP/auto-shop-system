import { Component, Input, OnChanges } from '@angular/core';
import { CnpjValidation, CpfValidation, Customer, Vehicle } from '../../../model/models';
import { CustomerService } from '../../../service/customer.service';
import { VehicleService } from '../../../service/vehicle.service';
import { CustomersComponent } from '../customers.component';

@Component({
  selector: 'app-customer-detail',
  templateUrl: './customer-detail.component.html',
  styleUrls: ['./customer-detail.component.css'],
})
export class CustomerDetailComponent implements OnChanges {
  @Input() customerId!: number;

  customer: Customer | undefined;
  vehicles: Vehicle[] = [];
  isCustomerChanged = false;
  creatingNewVehicle = false;
  newDocument = '';
  cnpjValidation: CnpjValidation | null = null;
  cpfValidation: CpfValidation | null = null;

  constructor(
    private customerService: CustomerService,
    private vehicleService: VehicleService,
    private parent: CustomersComponent
  ) {}

  ngOnChanges(): void {
    if (this.customerId) {
      this.isCustomerChanged = false;
      this.creatingNewVehicle = false;
      this.newDocument = '';
      this.cnpjValidation = null;
      this.cpfValidation = null;
      this.loadCustomer();
      this.loadVehicles();
    }
  }

  loadCustomer(): void {
    this.customerService.getById(this.customerId).subscribe((data) => {
      this.customer = data;
      this.isCustomerChanged = false;
    });
  }

  loadVehicles(): void {
    this.vehicleService.getByCustomer(this.customerId).subscribe((data) => {
      this.vehicles = data.sort((a, b) => a.id - b.id);
    });
  }

  customerChanged(): void {
    this.isCustomerChanged = true;
  }

  updateCustomer(): void {
    if (!this.customer) {
      return;
    }
    const body = {
      name: this.customer.name,
      email: this.customer.email,
      phone: this.customer.phone,
      address: this.customer.address,
    };
    this.customerService.update(this.customerId, body).subscribe((updated) => {
      this.customer = updated;
      this.isCustomerChanged = false;
      this.parent.updateCustomerInList(updated);
    });
  }

  looksLikeCpf(value: string): boolean {
    return value.replace(/\D/g, '').length === 11;
  }

  looksLikeCnpj(value: string): boolean {
    return value.replace(/\D/g, '').length === 14;
  }

  validateCpf(document: string): void {
    const cpf = document.replace(/\D/g, '');
    this.customerService.validateCpf(cpf).subscribe((result) => {
      this.cpfValidation = result;
      this.cnpjValidation = null;
    });
  }

  validateCnpj(document: string): void {
    const cnpj = document.replace(/\D/g, '');
    this.customerService.validateCnpj(cnpj).subscribe((result) => {
      this.cnpjValidation = result;
      this.cpfValidation = null;
    });
  }

  addDocument(): void {
    const document = this.newDocument.trim();
    if (!document) {
      return;
    }
    this.customerService.addDocument(this.customerId, document).subscribe((updated) => {
      this.customer = updated;
      this.newDocument = '';
      this.parent.updateCustomerInList(updated);
    });
  }

  showVehicleForm(): void {
    this.creatingNewVehicle = true;
  }

  onVehicleCreated(): void {
    this.creatingNewVehicle = false;
    this.loadVehicles();
  }

  onVehicleFormCancelled(): void {
    this.creatingNewVehicle = false;
  }
}
