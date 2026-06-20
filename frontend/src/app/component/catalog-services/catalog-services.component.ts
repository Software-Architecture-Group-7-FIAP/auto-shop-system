import { Component, OnInit } from '@angular/core';
import { CatalogService } from '../../model/models';
import { CatalogServiceService } from '../../service/catalog-service.service';

@Component({
  selector: 'app-catalog-services',
  templateUrl: './catalog-services.component.html',
  styleUrls: ['./catalog-services.component.css'],
})
export class CatalogServicesComponent implements OnInit {
  catalogServices: CatalogService[] = [];
  selectedCatalogServiceId: number | undefined;
  creatingNewCatalogService = false;

  constructor(private catalogServiceService: CatalogServiceService) {}

  ngOnInit(): void {
    this.catalogServiceService.getAll().subscribe((data) => {
      this.catalogServices = data.sort((a, b) => a.id - b.id);
    });
  }

  selectCatalogService(id: number): void {
    this.selectedCatalogServiceId = id;
    this.creatingNewCatalogService = false;
  }

  toCreatingMode = (): void => {
    this.selectedCatalogServiceId = undefined;
    this.creatingNewCatalogService = true;
  };

  updateCatalogServiceInList(catalogService: CatalogService): void {
    const index = this.catalogServices.findIndex((s) => s.id === catalogService.id);
    if (index >= 0) {
      this.catalogServices[index] = catalogService;
    }
  }
}
