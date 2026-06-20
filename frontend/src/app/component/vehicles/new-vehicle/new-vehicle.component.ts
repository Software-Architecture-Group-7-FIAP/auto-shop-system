import { Component } from '@angular/core';
import { VehicleService } from '../../../service/vehicle.service';

@Component({
  selector: 'app-new-vehicle',
  templateUrl: './new-vehicle.component.html',
  styleUrls: ['./new-vehicle.component.css'],
})
export class NewVehicleComponent {
  constructor(private vehicleService: VehicleService) {}

  saveVehicle(data: {
    customer_id: string;
    plate: string;
    brand: string;
    model: string;
    year: string;
  }): void {
    const body = {
      customer_id: Number(data.customer_id),
      plate: data.plate.trim(),
      brand: data.brand.trim(),
      model: data.model.trim(),
      year: Number(data.year),
    };
    this.vehicleService.create(body).subscribe(() => {
      window.location.reload();
    });
  }
}
