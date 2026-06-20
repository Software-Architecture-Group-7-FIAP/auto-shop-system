import { Component, OnInit } from '@angular/core';
import { Vehicle } from '../../model/models';
import { VehicleService } from '../../service/vehicle.service';

@Component({
  selector: 'app-vehicles',
  templateUrl: './vehicles.component.html',
  styleUrls: ['./vehicles.component.css'],
})
export class VehiclesComponent implements OnInit {
  vehicles: Vehicle[] = [];
  selectedVehicleId: number | undefined;
  creatingNewVehicle = false;

  constructor(private vehicleService: VehicleService) {}

  ngOnInit(): void {
    this.vehicleService.getAll().subscribe((data) => {
      this.vehicles = data.sort((a, b) => a.id - b.id);
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
