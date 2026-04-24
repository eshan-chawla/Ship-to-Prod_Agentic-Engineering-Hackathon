export type Supplier = {
  id: number;
  name: string;
  website: string;
  country: string;
  category: string;
  criticality: string;
  created_at: string;
};

export type FactorDetail = {
  score: number;
  confidence: number;
  evidence_ids: number[];
};

export type SupplierRisk = {
  id: number;
  supplier_id: number;
  scan_id: number;
  score: number;
  financial_stress: number;
  legal_regulatory: number;
  delivery_disruption: number;
  sentiment: number;
  cybersecurity: number;
  geopolitical: number;
  factor_details: Record<string, FactorDetail>;
  explanation: string;
  created_at: string;
};

export type Product = {
  id: number;
  name: string;
  brand: string;
  category: string;
  target_price: number;
  target_margin: number;
  created_at: string;
};

export type CompetitorUrl = {
  id: number;
  product_id: number;
  competitor_name: string;
  url: string;
  created_at: string;
};

export type PriceObservation = {
  id: number;
  product_id: number;
  competitor_url_id: number;
  competitor_name: string;
  url: string;
  price: number;
  stock_status: string;
  promo_signal: string;
  observed_at: string;
};

export type PricingAction =
  | "HOLD_PRICE"
  | "LOWER_PRICE"
  | "RAISE_PRICE"
  | "LAUNCH_PROMO"
  | "INVESTIGATE"
  | string;

export type PriceRecommendation = {
  id: number;
  product_id: number;
  action: PricingAction;
  explanation: string;
  expected_impact: string | null;
  confidence: number;
  created_at: string;
};

export const PRICING_ACTION_LABELS: Record<string, string> = {
  HOLD_PRICE: "Hold price",
  LOWER_PRICE: "Lower price",
  RAISE_PRICE: "Raise price",
  LAUNCH_PROMO: "Launch promo",
  INVESTIGATE: "Investigate",
};

export function pricingActionLabel(action: string): string {
  return PRICING_ACTION_LABELS[action] ?? action;
}

export type Alert = {
  id: number;
  entity_type: string;
  entity_id: number;
  severity: string;
  title: string;
  message: string;
  created_at: string;
  acknowledged_at: string | null;
};

export type AgentRun = {
  id: number;
  run_type: string;
  entity_type: string;
  entity_id: number;
  status: string;
  started_at: string;
  ended_at: string | null;
  summary: string | null;
};

export type Evidence = {
  id: number;
  entity_type: string;
  entity_id: number;
  scan_id: number | null;
  source_url: string;
  source_title: string;
  content: string;
  evidence_type: string;
  risk_factor: string | null;
  captured_at: string;
};

export type Dashboard = {
  suppliers: number;
  products: number;
  open_alerts: number;
  agent_runs: number;
  latest_risks: SupplierRisk[];
  latest_recommendations: PriceRecommendation[];
  recent_alerts: Alert[];
  recent_agent_runs: AgentRun[];
};

const serverBaseUrl = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const browserBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${serverBaseUrl}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API ${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function money(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export function dateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

