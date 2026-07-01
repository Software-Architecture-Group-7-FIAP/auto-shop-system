import { Component, EventEmitter, Input, Output } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { VehicleService } from '../../../service/vehicle.service';
import { extractApiErrorMessage } from '../../../util/api-error';
import { validateVehicleForm } from '../../../util/vehicle-form';

@Component({
  selector: 'app-new-vehicle',
  templateUrl: './new-vehicle.component.html',
  styleUrls: ['./new-vehicle.component.css'],
})
export class NewVehicleComponent {
  @Input() customerId?: number;
  @Output() vehicleCreated = new EventEmitter<void>();
  @Output() cancelled = new EventEmitter<void>();

  errorMessage = '';
  errorTitle = 'Não foi possível cadastrar o veículo';

  constructor(private vehicleService: VehicleService) {}

  clearError(): void {
    this.errorMessage = '';
  }

  saveVehicle(data: {
    customer_id?: string;
    plate: string;
    state: string;
    city: string;
    color: string;
    brand: string;
    model: string;
    year: string;
  }): void {
    const validation = validateVehicleForm(
      {
        customer_id: this.customerId ?? data.customer_id,
        plate: data.plate,
        state: data.state,
        city: data.city,
        color: data.color,
        brand: data.brand,
        model: data.model,
        year: data.year,
      },
      { requirePlate: true, requireCustomerId: !this.customerId }
    );

    if ('error' in validation) {
      this.errorTitle = 'Dados inválidos no formulário';
      this.errorMessage = validation.error;
      return;
    }

    const { data: body } = validation;
    this.errorMessage = '';
    this.vehicleService
      .create({
        customer_id: this.customerId ?? body.customer_id,
        plate: body.plate,
        state: body.state,
        city: body.city,
        color: body.color,
        brand: body.brand,
        model: body.model,
        year: body.year,
      })
      .subscribe({
        next: () => {
          if (this.customerId) {
            this.vehicleCreated.emit();
          } else {
            window.location.reload();
          }
        },
        error: (error: HttpErrorResponse) => {
          this.errorTitle = 'Não foi possível cadastrar o veículo';
          this.errorMessage = extractApiErrorMessage(
            error,
            'Não foi possível salvar o veículo.'
          );
        },
      });
  }

  cancel(): void {
    this.cancelled.emit();
  }
}
