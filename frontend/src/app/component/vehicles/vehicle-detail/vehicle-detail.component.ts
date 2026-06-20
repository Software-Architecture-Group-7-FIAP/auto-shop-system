import { Component, Input, OnChanges } from '@angular/core';
import { Vehicle } from '../../../model/models';
import { VehicleService } from '../../../service/vehicle.service';
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

  constructor(
    private vehicleService: VehicleService,
    private parent: VehiclesComponent
  ) {}

  ngOnChanges(): void {
    if (this.vehicleId) {
      this.isVehicleChanged = false;
      this.loadVehicle();
    }
  }

  loadVehicle(): void {
    this.vehicleService.getById(this.vehicleId).subscribe((data) => {
      this.vehicle = data;
      this.isVehicleChanged = false;
    });
  }

  vehicleChanged(): void {
    this.isVehicleChanged = true;
  }

  updateVehicle(): void {
    if (!this.vehicle) {
      return;
    }
    const body = {
      brand: this.vehicle.brand,
      model: this.vehicle.model,
      year: this.vehicle.year,
    };
    this.vehicleService.update(this.vehicleId, body).subscribe((updated) => {
      this.vehicle = updated;
      this.isVehicleChanged = false;
      this.parent.updateVehicleInList(updated);
    });
  }
}
