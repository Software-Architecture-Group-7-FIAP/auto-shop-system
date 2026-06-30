import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { AuthGuard } from './service/auth.guard';

import { LoginComponent } from './component/login/login.component';
import { MenuComponent } from './component/menu/menu.component';
import { CustomersComponent } from './component/customers/customers.component';
import { VehiclesComponent } from './component/vehicles/vehicles.component';
import { CatalogServicesComponent } from './component/catalog-services/catalog-services.component';
import { ProductsComponent } from './component/products/products.component';
import { SuppliersComponent } from './component/suppliers/suppliers.component';
import { BudgetsComponent } from './component/budgets/budgets.component';
import { ServiceOrdersComponent } from './component/service-orders/service-orders.component';
import { ServiceOrderTrackingComponent } from './component/service-order-tracking/service-order-tracking.component';
import { BudgetApprovalComponent } from './component/budget-approval/budget-approval.component';

const routes: Routes = [
  { path: '', redirectTo: '/menu', pathMatch: 'full' },
  { path: 'login', component: LoginComponent },
  { path: 'budget-approval', component: BudgetApprovalComponent },
  { path: 'track-service-order', component: ServiceOrderTrackingComponent },
  { path: 'menu', component: MenuComponent, canActivate: [AuthGuard] },
  { path: 'customers', component: CustomersComponent, canActivate: [AuthGuard] },
  { path: 'vehicles', component: VehiclesComponent, canActivate: [AuthGuard] },
  { path: 'catalog-services', component: CatalogServicesComponent, canActivate: [AuthGuard] },
  { path: 'products', component: ProductsComponent, canActivate: [AuthGuard] },
  { path: 'suppliers', component: SuppliersComponent, canActivate: [AuthGuard] },
  { path: 'budgets', component: BudgetsComponent, canActivate: [AuthGuard] },
  { path: 'service-orders', component: ServiceOrdersComponent, canActivate: [AuthGuard] },
  { path: '**', redirectTo: '/menu' },
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule],
})
export class AppRoutingModule {}
