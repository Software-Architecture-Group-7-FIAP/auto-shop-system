import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { HTTP_INTERCEPTORS, HttpClientModule } from '@angular/common/http';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';

import { LoginComponent } from './component/login/login.component';
import { MenuComponent } from './component/menu/menu.component';
import { HeadNavigationComponent } from './component/head-navigation/head-navigation.component';

import { CustomersComponent } from './component/customers/customers.component';
import { CustomerDetailComponent } from './component/customers/customer-detail/customer-detail.component';
import { NewCustomerComponent } from './component/customers/new-customer/new-customer.component';

import { VehiclesComponent } from './component/vehicles/vehicles.component';
import { VehicleDetailComponent } from './component/vehicles/vehicle-detail/vehicle-detail.component';
import { NewVehicleComponent } from './component/vehicles/new-vehicle/new-vehicle.component';

import { CatalogServicesComponent } from './component/catalog-services/catalog-services.component';
import { CatalogServiceDetailComponent } from './component/catalog-services/catalog-service-detail/catalog-service-detail.component';
import { NewCatalogServiceComponent } from './component/catalog-services/new-catalog-service/new-catalog-service.component';

import { ProductsComponent } from './component/products/products.component';
import { ProductDetailComponent } from './component/products/product-detail/product-detail.component';
import { NewProductComponent } from './component/products/new-product/new-product.component';

import { SuppliersComponent } from './component/suppliers/suppliers.component';
import { SupplierDetailComponent } from './component/suppliers/supplier-detail/supplier-detail.component';
import { NewSupplierComponent } from './component/suppliers/new-supplier/new-supplier.component';

import { BudgetsComponent } from './component/budgets/budgets.component';
import { BudgetDetailComponent } from './component/budgets/budget-detail/budget-detail.component';
import { NewBudgetComponent } from './component/budgets/new-budget/new-budget.component';

import { ServiceOrdersComponent } from './component/service-orders/service-orders.component';
import { ServiceOrderDetailComponent } from './component/service-orders/service-order-detail/service-order-detail.component';
import { ServiceOrderTrackingComponent } from './component/service-order-tracking/service-order-tracking.component';

import { AuthInterceptor } from './service/auth.interceptor';
import { HttpErrorInterceptor } from './service/http-error.interceptor';

@NgModule({
  declarations: [
    AppComponent,
    LoginComponent,
    MenuComponent,
    HeadNavigationComponent,
    CustomersComponent,
    CustomerDetailComponent,
    NewCustomerComponent,
    VehiclesComponent,
    VehicleDetailComponent,
    NewVehicleComponent,
    CatalogServicesComponent,
    CatalogServiceDetailComponent,
    NewCatalogServiceComponent,
    ProductsComponent,
    ProductDetailComponent,
    NewProductComponent,
    SuppliersComponent,
    SupplierDetailComponent,
    NewSupplierComponent,
    BudgetsComponent,
    BudgetDetailComponent,
    NewBudgetComponent,
    ServiceOrdersComponent,
    ServiceOrderDetailComponent,
    ServiceOrderTrackingComponent,
  ],
  imports: [BrowserModule, FormsModule, AppRoutingModule, HttpClientModule],
  providers: [
    { provide: HTTP_INTERCEPTORS, useClass: AuthInterceptor, multi: true },
    { provide: HTTP_INTERCEPTORS, useClass: HttpErrorInterceptor, multi: true },
  ],
  bootstrap: [AppComponent],
})
export class AppModule {}
