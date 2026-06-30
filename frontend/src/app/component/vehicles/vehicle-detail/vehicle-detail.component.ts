import { Component, Input, OnChanges } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Vehicle } from '../../../model/models';
import { VehicleService } from '../../../service/vehicle.service';
import { extractApiErrorMessage } from '../../../util/api-error';
import { validateVehicleForm } from '../../../util/vehicle-form';
import { VehiclesComponent } from '../vehicles.component';

@Component({
  selector: 'app-vehicle-detail',
  templateUrl: './vehicle-detail.component.html',
  styleUrls: ['./vehicle-detail.component.css'],
})
export class VehicleDetailComponent implements OnChanges {
  @Input() vehicleId!: number;

  vehicle: Vehicle | undefined;
  isVehicleChanged = false;
  errorMessage = '';
  errorTitle = 'Não foi possível atualizar o veículo';

  constructor(
    private vehicleService: VehicleService,
    private parent: VehiclesComponent
  ) {}

  ngOnChanges(): void {
    if (this.vehicleId) {
      this.isVehicleChanged = false;
      this.clearError();
      this.loadVehicle();
    }
  }

  loadVehicle(): void {
    this.vehicleService.getById(this.vehicleId).subscribe({
      next: (data) => {
        this.vehicle = data;
        this.isVehicleChanged = false;
      },
      error: (error: HttpErrorResponse) => {
        this.errorTitle = 'Não foi possível carregar o veículo';
        this.errorMessage = extractApiErrorMessage(error);
      },
    });
  }

  vehicleChanged(): void {
    this.isVehicleChanged = true;
    this.clearError();
  }

  clearError(): void {
    this.errorMessage = '';
  }

  updateVehicle(): void {
    if (!this.vehicle) {
      return;
    }

    const validation = validateVehicleForm(
      {
        state: this.vehicle.state,
        city: this.vehicle.city,
        color: this.vehicle.color,
        brand: this.vehicle.brand,
        model: this.vehicle.model,
        year: this.vehicle.year,
      },
      { requirePlate: false }
    );

    if ('error' in validation) {
      this.errorTitle = 'Dados inválidos no formulário';
      this.errorMessage = validation.error;
      return;
    }

    const { data: body } = validation;
    this.errorMessage = '';
    this.vehicleService.update(this.vehicleId, body).subscribe({
      next: (updated) => {
        this.vehicle = updated;
        this.isVehicleChanged = false;
        this.parent.updateVehicleInList(updated);
      },
      error: (error: HttpErrorResponse) => {
        this.errorTitle = 'Não foi possível atualizar o veículo';
        this.errorMessage = extractApiErrorMessage(
          error,
          'Não foi possível atualizar o veículo.'
        );
      },
    });
  }
}
