import { Component, Input, OnChanges } from '@angular/core';
import { CatalogService } from '../../../model/models';
import { CatalogServiceService } from '../../../service/catalog-service.service';
import { CatalogServicesComponent } from '../catalog-services.component';

@Component({
  selector: 'app-catalog-service-detail',
  templateUrl: './catalog-service-detail.component.html',
  styleUrls: ['./catalog-service-detail.component.css'],
})
export class CatalogServiceDetailComponent implements OnChanges {
  @Input() catalogServiceId!: number;

  catalogService: CatalogService | undefined;
  isCatalogServiceChanged = false;

  constructor(
    private catalogServiceService: CatalogServiceService,
    private parent: CatalogServicesComponent
  ) {}

  ngOnChanges(): void {
    if (this.catalogServiceId) {
      this.isCatalogServiceChanged = false;
      this.loadCatalogService();
    }
  }

  loadCatalogService(): void {
    this.catalogServiceService.getById(this.catalogServiceId).subscribe((data) => {
      this.catalogService = data;
      this.isCatalogServiceChanged = false;
    });
  }

  catalogServiceChanged(): void {
    this.isCatalogServiceChanged = true;
  }

  updateCatalogService(): void {
    if (!this.catalogService) {
      return;
    }
    const body = {
      name: this.catalogService.name,
      description: this.catalogService.description,
      base_price: this.catalogService.base_price,
      estimated_hours: this.catalogService.estimated_hours,
    };
    this.catalogServiceService.update(this.catalogServiceId, body).subscribe((updated) => {
      this.catalogService = updated;
      this.isCatalogServiceChanged = false;
      this.parent.updateCatalogServiceInList(updated);
    });
  }
}
