export interface VehicleFormInput {
  plate?: string;
  state: string;
  city: string;
  color: string;
  brand: string;
  model: string;
  year: string | number;
  customer_id?: string | number;
}

export interface NormalizedVehicleForm {
  plate?: string;
  state: string;
  city: string;
  color: string;
  brand: string;
  model: string;
  year: number;
  customer_id?: number;
}

export function normalizePlate(raw: string): string {
  return raw.trim().toUpperCase().replace(/[-\s]/g, '');
}

export function validateVehicleForm(
  input: VehicleFormInput,
  options: { requirePlate?: boolean; requireCustomerId?: boolean } = {}
): { error: string } | { data: NormalizedVehicleForm } {
  const requirePlate = options.requirePlate ?? true;
  const requireCustomerId = options.requireCustomerId ?? false;

  let customer_id: number | undefined;
  if (requireCustomerId || input.customer_id !== undefined) {
    customer_id = Number(input.customer_id);
    if (!customer_id || Number.isNaN(customer_id)) {
      return { error: 'Informe um ID de cliente válido.' };
    }
  }

  const plate = input.plate ? normalizePlate(input.plate) : undefined;
  if (requirePlate) {
    if (!plate) {
      return { error: 'A placa é obrigatória.' };
    }
  }

  const state = input.state.trim().toUpperCase();
  if (state.length !== 2) {
    return { error: 'UF inválida. Informe 2 letras (ex.: SP, RJ).' };
  }

  const city = input.city.trim();
  const color = input.color.trim();
  const brand = input.brand.trim();
  const model = input.model.trim();
  if (!city) {
    return { error: 'A cidade é obrigatória.' };
  }
  if (!color) {
    return { error: 'A cor é obrigatória.' };
  }
  if (!brand) {
    return { error: 'A marca é obrigatória.' };
  }
  if (!model) {
    return { error: 'O modelo é obrigatório.' };
  }

  const year = Number(input.year);
  if (!Number.isInteger(year) || year < 1900 || year > 2100) {
    return { error: 'Ano inválido. Informe um valor entre 1900 e 2100.' };
  }

  return {
    data: {
      plate,
      state,
      city,
      color,
      brand,
      model,
      year,
      customer_id,
    },
  };
}
