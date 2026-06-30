import { Component, EventEmitter, Input, Output } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { VehicleService } from '../../../service/vehicle.service';

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

  constructor(private vehicleService: VehicleService) {}

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
    const resolvedCustomerId = this.customerId ?? Number(data.customer_id);
    if (!resolvedCustomerId) {
      this.errorMessage = 'Cliente é obrigatório';
      return;
    }

    const body = {
      customer_id: resolvedCustomerId,
      plate: data.plate.trim(),
      state: data.state.trim(),
      city: data.city.trim(),
      color: data.color.trim(),
      brand: data.brand.trim(),
      model: data.model.trim(),
      year: Number(data.year),
    };

    this.errorMessage = '';
    this.vehicleService.create(body).subscribe({
      next: () => {
        if (this.customerId) {
          this.vehicleCreated.emit();
        } else {
          window.location.reload();
        }
      },
      error: (error: HttpErrorResponse) => {
        this.errorMessage = this.extractErrorMessage(error);
      },
    });
  }

  cancel(): void {
    this.cancelled.emit();
  }

  private extractErrorMessage(error: HttpErrorResponse): string {
    const detail = error.error?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((item: { msg?: string }) => item.msg ?? '').join('; ');
    }
    return 'Não foi possível salvar o veículo';
  }
}
