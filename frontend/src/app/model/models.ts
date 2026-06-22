export enum BudgetStatus {
  DRAFT = 'Rascunho',
  SENT = 'Enviado',
  APPROVED = 'Aprovado',
  REJECTED = 'Recusado',
}

export enum ServiceOrderStatus {
  RECEBIDA = 'Recebida',
  EM_DIAGNOSTICO = 'Em diagnóstico',
  AGUARDANDO_APROVACAO = 'Aguardando aprovação',
  EM_EXECUCAO = 'Em execução',
  FINALIZADA = 'Finalizada',
  ENTREGUE = 'Entregue',
}

export enum Priority {
  LOW = 'Baixa',
  NORMAL = 'Normal',
  HIGH = 'Alta',
  URGENT = 'Urgente',
}

export enum InvoiceStatus {
  PENDING = 'Pendente',
  PAID = 'Paga',
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface Customer {
  id: number;
  name: string;
  documents: string[];
  email: string;
  phone: string | null;
  address: string;
  created_at: string;
}

export interface Vehicle {
  id: number;
  customer_id: number;
  plate: string;
  brand: string;
  model: string;
  year: number;
  created_at: string;
}

export interface CatalogService {
  id: number;
  name: string;
  description: string | null;
  base_price: number;
  estimated_hours: number;
  created_at: string;
}

export interface Product {
  id: number;
  name: string;
  sku: string;
  unit_price: number;
  stock_quantity: number;
  description: string | null;
  supplier_id: number | null;
  created_at: string;
}

export interface Supplier {
  id: number;
  name: string;
  document: string;
  email: string;
  phone: string | null;
  created_at: string;
}

export interface Budget {
  id: number;
  customer_id: number;
  vehicle_id: number;
  status: BudgetStatus;
  total_price: number;
  estimated_delivery: string | null;
  approval_token: string | null;
  created_at: string;
}

export interface BudgetServiceLine {
  id: number;
  service_id: number;
  service_name: string;
  quantity: number;
}

export interface BudgetProductLine {
  id: number;
  product_id: number;
  product_name: string;
  quantity: number;
}

export interface ServiceOrder {
  id: number;
  budget_id: number | null;
  customer_id: number;
  vehicle_id: number;
  status: ServiceOrderStatus;
  priority: Priority;
  mechanic_name: string | null;
  total_price: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface CnpjValidation {
  valid: boolean;
  legal_name: string | null;
  trade_name: string | null;
}

export interface CpfValidation {
  valid: boolean;
  formatted: string | null;
}

export interface AvailabilityItem {
  product_id: number;
  product_name: string;
  required: number;
  available: number;
  sufficient: boolean;
}

export interface MessageResponse {
  message: string;
}

export interface AverageExecutionTime {
  average_hours: number;
  sample_size: number;
}

export interface Invoice {
  id: number;
  service_order_id: number;
  amount: number;
  status: InvoiceStatus;
  paid_at: string | null;
  created_at: string;
}
