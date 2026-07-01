import { Component, OnInit } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Vehicle } from '../../model/models';
import { VehicleService } from '../../service/vehicle.service';
import { extractApiErrorMessage } from '../../util/api-error';

@Component({
  selector: 'app-vehicles',
  templateUrl: './vehicles.component.html',
  styleUrls: ['./vehicles.component.css'],
})
export class VehiclesComponent implements OnInit {
  vehicles: Vehicle[] = [];
  selectedVehicleId: number | undefined;
  creatingNewVehicle = false;
  loadErrorMessage = '';
  loadErrorTitle = 'Não foi possível carregar os veículos';

  constructor(private vehicleService: VehicleService) {}

  ngOnInit(): void {
    this.loadVehicles();
  }

  loadVehicles(): void {
    this.loadErrorMessage = '';
    this.vehicleService.getAll().subscribe({
      next: (data) => {
        this.vehicles = data.sort((a, b) => a.id - b.id);
      },
      error: (error: HttpErrorResponse) => {
        this.loadErrorMessage = extractApiErrorMessage(
          error,
          'Não foi possível carregar a lista de veículos.'
        );
      },
    });
  }

  selectVehicle(id: number): void {
    this.selectedVehicleId = id;
    this.creatingNewVehicle = false;
  }

  toCreatingMode = (): void => {
    this.selectedVehicleId = undefined;
    this.creatingNewVehicle = true;
  };

  updateVehicleInList(vehicle: Vehicle): void {
    const index = this.vehicles.findIndex((v) => v.id === vehicle.id);
    if (index >= 0) {
      this.vehicles[index] = vehicle;
    }
  }
}
