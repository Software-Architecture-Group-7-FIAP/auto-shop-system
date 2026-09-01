export enum BudgetStatus {
  DRAFT = 'Rascunho',
  SENT = 'Enviado',
  APPROVED = 'Aprovado',
  REJECTED = 'Recusado',
  SUPERSEDED = 'Substitu\u00eddo',
}

export enum ServiceOrderStatus {
  RECEBIDA = 'Recebida',
  EM_DIAGNOSTICO = 'Em diagn\u00f3stico',
  AGUARDANDO_APROVACAO = 'Aguardando aprova\u00e7\u00e3o',
  AGUARDANDO_INICIO = 'Aguardando in\u00edcio',
  EM_EXECUCAO = 'Em execu\u00e7\u00e3o',
  FINALIZADA = 'Finalizada',
  ENTREGUE = 'Entregue',
}

export enum Priority {
  LOW = 'Baixa',
  NORMAL = 'Normal',
  HIGH = 'Alta',
  URGENT = 'Urgente',
}

export enum InvoiceStatus { PENDING = 'Pendente', PAID = 'Paga' }
export interface SessionResponse { username: string; role: 'ADMIN' | 'OPERATOR'; }
export interface LoginRequest { username: string; password: string; }
export interface Customer { id: number; name: string; documents: string[]; email: string; phone: string | null; address: string; created_at: string; }
export interface Vehicle { id: number; customer_id: number; plate: string; state: string; city: string; color: string; brand: string; model: string; year: number; created_at: string; }
export interface CatalogService { id: number; name: string; description: string | null; base_price: number; estimated_hours: number; created_at: string; product_lines: ServiceProductLine[]; }
export interface ServiceProductLine { id: number; service_id: number; product_id: number; quantity: number; }
export interface Product { id: number; name: string; sku: string; unit_price: number; stock_quantity: number; description: string | null; supplier_id: number; created_at: string; }
export interface Supplier { id: number; name: string; document: string; email: string; phone: string | null; created_at: string; }
export interface Budget { id: number; customer_id: number; vehicle_id: number; status: BudgetStatus; total_price: number; estimated_delivery: string | null; created_at: string; revision_number: number; supersedes_budget_id: number | null; }
export interface BudgetServiceLine { id: number; service_id: number; service_name: string; quantity: number; unit_price: number; }
export interface BudgetProductLine { id: number; product_id: number; product_name: string; quantity: number; unit_price: number; }
export interface ServiceOrder { id: number; budget_id: number | null; customer_id: number; vehicle_id: number; status: ServiceOrderStatus; priority: Priority; mechanic_name: string | null; total_price: number; started_at: string | null; finished_at: string | null; created_at: string; }
export interface ServiceOrderPublic { id: number; status: ServiceOrderStatus; started_at: string | null; finished_at: string | null; created_at: string; }
export interface ServiceOrderUpdate { mechanic_name?: string; priority?: Priority; reason?: string; }
export interface ServiceOrderStatusOverride { status: ServiceOrderStatus; reason: string; }
export interface AvailabilityItem { product_id: number; product_name: string; required: number; available: number; sufficient: boolean; }
export interface MessageResponse { message: string; status?: BudgetStatus; already_processed?: boolean; service_order_id?: number | null; }
export interface CnpjValidation { valid: boolean; legal_name?: string; trade_name?: string; }
export interface CpfValidation { valid: boolean; formatted?: string; }
export interface AverageExecutionTime { average_hours: number; sample_size: number; }
export interface Invoice { id: number; service_order_id: number; amount: number; status: InvoiceStatus; paid_at: string | null; created_at: string; }
