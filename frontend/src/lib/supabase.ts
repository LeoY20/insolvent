import { createClient } from '@supabase/supabase-js'

// --- Supabase Client Initialization ---
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || import.meta.env.SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || import.meta.env.SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.error('Supabase URL or Anon Key is missing in environment variables.')
  // In a real application, you might want to throw an error or handle this more gracefully.
  // For now, we'll ensure supabase is not used if keys are missing.
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// --- Interfaces ---
export interface Alert {
  id: string
  created_at: string
  title: string
  description: string
  severity: 'CRITICAL' | 'URGENT' | 'WARNING' | 'INFO'
  alert_type: 'RESTOCK_NOW' | 'SHORTAGE_WARNING' | 'SUBSTITUTE_RECOMMENDED' | 'SCHEDULE_CHANGE' | 'SUPPLY_CHAIN_RISK' | 'AUTO_ORDER_PLACED'
  drug_name: string
  acknowledged: boolean
}

export interface Drug {
  id: string
  created_at: string
  name: string
  type: string
  criticality_rank: number
  stock_quantity: number
  usage_rate_daily: number
  burn_rate_days: number | null
  price_per_unit: number | null
  supplier_id: string | null
  unit?: string
  predicted_usage_rate?: number | null
  predicted_burn_rate_days?: number | null
  reorder_threshold_days?: number | null
}

export interface Shortage {
  id: string
  created_at: string
  drug_id: string
  drug_name: string
  reason: string
  estimated_resolution: string | null
  resolved: boolean
  reported_date?: string
  impact_severity?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  description?: string
  source?: string
  type?: string
}

export interface Substitute {
  id: string
  created_at: string
  drug_name: string
  substitute_name: string
  preference_rank: number
  equivalence_notes?: string
}

export interface Supplier {
  id: string
  created_at: string
  name: string
  drug_name: string
  location?: string
  price_per_unit: number
  lead_time_days: number | null
  reliability_score: number
  is_nearby_hospital: boolean
  active: boolean
}

// --- Utility Functions ---

export function getSeverityColor(severity: Alert['severity']): string {
  switch (severity) {
    case 'CRITICAL':
      return 'border-red-400 text-red-800 bg-red-100'
    case 'URGENT':
      return 'border-orange-400 text-orange-800 bg-orange-100'
    case 'WARNING':
      return 'border-yellow-400 text-yellow-800 bg-yellow-100'
    case 'INFO':
      return 'border-blue-400 text-blue-800 bg-blue-100'
    default:
      return 'border-gray-400 text-gray-800 bg-gray-100'
  }
}

export function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return 'N/A'
  return new Intl.NumberFormat().format(num)
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return 'N/A'
  try {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  } catch {
    return 'N/A'
  }
}

export function getBurnRateColor(burnRateDays: number | null | undefined): string {
  if (burnRateDays === null || burnRateDays === undefined) return 'text-gray-500'
  if (burnRateDays < 7) {
    return 'text-red-600 font-semibold'
  } else if (burnRateDays < 14) {
    return 'text-orange-600 font-semibold'
  } else if (burnRateDays < 30) {
    return 'text-yellow-600'
  }
  return 'text-green-600'
}

export function getBurnRateBgColor(burnRateDays: number | null | undefined): string {
  if (burnRateDays === null || burnRateDays === undefined) return ''
  if (burnRateDays < 7) {
    return 'bg-red-50'
  } else if (burnRateDays < 14) {
    return 'bg-orange-50'
  } else if (burnRateDays < 30) {
    return 'bg-yellow-50'
  }
  return ''
}

export function getImpactSeverityColor(severity: Shortage['impact_severity']): string {
  switch (severity) {
    case 'CRITICAL':
      return 'border-red-400 text-red-800 bg-red-100'
    case 'HIGH':
      return 'border-orange-400 text-orange-800 bg-orange-100'
    case 'MEDIUM':
      return 'border-yellow-400 text-yellow-800 bg-yellow-100'
    case 'LOW':
      return 'border-blue-400 text-blue-800 bg-blue-100'
    default:
      return 'border-gray-400 text-gray-800 bg-gray-100'
  }
}
