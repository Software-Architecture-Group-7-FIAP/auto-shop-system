import { Component } from '@angular/core';
import { CatalogServiceService } from '../../../service/catalog-service.service';

@Component({
  selector: 'app-new-catalog-service',
  templateUrl: './new-catalog-service.component.html',
  styleUrls: ['./new-catalog-service.component.css'],
})
export class NewCatalogServiceComponent {
  constructor(private catalogServiceService: CatalogServiceService) {}

  saveCatalogService(data: {
    name: string;
    description: string;
    base_price: string;
    estimated_hours: string;
  }): void {
    const body = {
      name: data.name.trim(),
      description: data.description?.trim() || null,
      base_price: Number(data.base_price),
      estimated_hours: Number(data.estimated_hours) || 1,
    };
    this.catalogServiceService.create(body).subscribe(() => {
      window.location.reload();
    });
  }
}
