import { createClient } from '@supabase/supabase-js'

// ============================================================================
// TypeScript Interfaces for Database Tables
// ============================================================================

export interface Drug {
  id: string
  name: string
  type: string
  stock_quantity: number
  unit: string
  price_per_unit: number | null
  primary_supplier_id: string | null
  usage_rate_daily: number
  predicted_usage_rate: number | null
  burn_rate_days: number | null
  predicted_burn_rate_days: number | null
  reorder_threshold_days: number
  criticality_rank: number
  last_restock_date: string | null
  created_at: string
  updated_at: string
}

export interface Shortage {
  id: string
  drug_name: string
  drug_id: string | null
  type: string
  source: string
  source_url: string | null
  impact_severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  description: string | null
  reported_date: string
  resolved: boolean
  resolved_date: string | null
  created_at: string
}

export interface Supplier {
  id: string
  name: string
  drug_name: string
  drug_id: string | null
  price_per_unit: number | null
  location: string | null
  lead_time_days: number | null
  reliability_score: number
  contact_info: string | null
  is_nearby_hospital: boolean
  active: boolean
  created_at: string
}

export interface Substitute {
  id: string
  drug_id: string
  drug_name: string
  substitute_name: string
  substitute_drug_id: string | null
  equivalence_notes: string | null
  preference_rank: number
  created_at: string
}

export interface AgentLog {
  id: string
  agent_name: string
  run_id: string
  payload: Record<string, any>
  summary: string | null
  created_at: string
}

export interface Alert {
  id: string
  run_id: string
  alert_type: 'RESTOCK_NOW' | 'SHORTAGE_WARNING' | 'SUBSTITUTE_RECOMMENDED' | 'SCHEDULE_CHANGE' | 'SUPPLY_CHAIN_RISK' | 'AUTO_ORDER_PLACED'
  severity: 'INFO' | 'WARNING' | 'URGENT' | 'CRITICAL'
  drug_id: string | null
  drug_name: string
  title: string
  description: string
  action_payload: Record<string, any> | null
  acknowledged: boolean
  created_at: string
}

export interface SurgerySchedule {
  id: string
  surgery_type: string
  scheduled_date: string
  estimated_duration_hours: number | null
  drugs_required: Array<{
    drug_name: string
    quantity: number
    unit: string
  }>
  status: 'SCHEDULED' | 'COMPLETED' | 'CANCELLED' | 'RESCHEDULED'
  created_at: string
}

// ============================================================================
// Database Schema Type
// ============================================================================

export interface Database {
  public: {
    Tables: {
      drugs: {
        Row: Drug
        Insert: Omit<Drug, 'id' | 'created_at' | 'updated_at'>
        Update: Partial<Omit<Drug, 'id' | 'created_at' | 'updated_at'>>
      }
      shortages: {
        Row: Shortage
        Insert: Omit<Shortage, 'id' | 'created_at'>
        Update: Partial<Omit<Shortage, 'id' | 'created_at'>>
      }
      suppliers: {
        Row: Supplier
        Insert: Omit<Supplier, 'id' | 'created_at'>
        Update: Partial<Omit<Supplier, 'id' | 'created_at'>>
      }
      substitutes: {
        Row: Substitute
        Insert: Omit<Substitute, 'id' | 'created_at'>
        Update: Partial<Omit<Substitute, 'id' | 'created_at'>>
      }
      agent_logs: {
        Row: AgentLog
        Insert: Omit<AgentLog, 'id' | 'created_at'>
        Update: Partial<Omit<AgentLog, 'id' | 'created_at'>>
      }
      alerts: {
        Row: Alert
        Insert: Omit<Alert, 'id' | 'created_at'>
        Update: Partial<Omit<Alert, 'id' | 'created_at'>>
      }
      surgery_schedule: {
        Row: SurgerySchedule
        Insert: Omit<SurgerySchedule, 'id' | 'created_at'>
        Update: Partial<Omit<SurgerySchedule, 'id' | 'created_at'>>
      }
    }
  }
}

// ============================================================================
// Supabase Client
// ============================================================================

// ============================================================================
// Supabase Client & Mock Implementation
// ============================================================================

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// Mock Data
const MOCK_DRUGS: Drug[] = [
  {
    id: 'd1',
    name: 'Epinephrine',
    type: 'Anaphylaxis/Cardiac',
    stock_quantity: 150,
    unit: 'vials',
    price_per_unit: 25.50,
    primary_supplier_id: null,
    usage_rate_daily: 5,
    predicted_usage_rate: 5.2,
    burn_rate_days: 30,
    predicted_burn_rate_days: 28.8,
    reorder_threshold_days: 14,
    criticality_rank: 1,
    last_restock_date: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'd2',
    name: 'Propofol',
    type: 'Anesthetic',
    stock_quantity: 20,
    unit: 'vials',
    price_per_unit: 12.00,
    primary_supplier_id: null,
    usage_rate_daily: 10,
    predicted_usage_rate: 12,
    burn_rate_days: 2,
    predicted_burn_rate_days: 1.6,
    reorder_threshold_days: 14,
    criticality_rank: 4,
    last_restock_date: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'd3',
    name: 'Oxygen',
    type: 'Respiratory',
    stock_quantity: 500,
    unit: 'tanks',
    price_per_unit: 45.00,
    primary_supplier_id: null,
    usage_rate_daily: 20,
    predicted_usage_rate: 20,
    burn_rate_days: 25,
    predicted_burn_rate_days: 25,
    reorder_threshold_days: 7,
    criticality_rank: 2,
    last_restock_date: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
]

const MOCK_ALERTS: Alert[] = [
  {
    id: 'a1',
    run_id: 'mock-run-1',
    alert_type: 'RESTOCK_NOW',
    severity: 'CRITICAL',
    drug_id: 'd2',
    drug_name: 'Propofol',
    title: 'Critical Low Stock: Propofol',
    description: 'Current stock will be depleted in < 48 hours based on predicted usage.',
    action_payload: null,
    acknowledged: false,
    created_at: new Date().toISOString()
  },
  {
    id: 'a2',
    run_id: 'mock-run-1',
    alert_type: 'SHORTAGE_WARNING',
    severity: 'WARNING',
    drug_id: 'd1',
    drug_name: 'Epinephrine',
    title: 'Potential Supply Chain Delay',
    description: 'News reports indicate manufacturing delays at major supplier facilities.',
    action_payload: null,
    acknowledged: false,
    created_at: new Date(Date.now() - 86400000).toISOString()
  }
]

class MockSupabaseClient {
  constructor() {
    console.warn('⚠️ USING MOCK SUPABASE CLIENT ⚠️')
  }

  from(table: string) {
    return {
      select: () => this.createBuilder(table),
      update: (_data: unknown) => this.createBuilder(table),
      insert: (_data: unknown) => this.createBuilder(table),
      upsert: (_data: unknown) => this.createBuilder(table),
      delete: () => this.createBuilder(table),
    }
  }

  channel(_name: string) {
    const mockChannel = {
      on: (_event: unknown, _filter: unknown, _callback: unknown) => {
        return mockChannel
      },
      subscribe: (callback?: (status: string, err?: Error) => void) => {
        if (callback) callback('SUBSCRIBED')
        return mockChannel
      },
      unsubscribe: () => { }
    }
    return mockChannel
  }

  removeChannel(_channel: unknown) {
    // Mock implementation - does nothing
  }

  private createBuilder(table: string) {
    const builder = {
      eq: () => builder,
      order: () => builder,
      limit: () => builder,
      single: () => builder,
      then: (resolve: (res: any) => void) => {
        let resultData: any = []
        if (table === 'drugs') resultData = [...MOCK_DRUGS]
        else if (table === 'alerts') resultData = [...MOCK_ALERTS]
        else if (table === 'shortages') resultData = []
        else if (table === 'suppliers') resultData = []

        // Simulate async
        setTimeout(() => {
          resolve({ data: resultData, error: null })
        }, 100)
      }
    }
    return builder
  }
}

const shouldMock = !supabaseUrl || !supabaseAnonKey || supabaseUrl.includes('your_supabase_project_url')

if (shouldMock) {
  console.log('Supabase credentials missing or invalid. Initializing Mock Client.')
}

export const supabase = shouldMock
  ? (new MockSupabaseClient() as any)
  : createClient<Database>(supabaseUrl, supabaseAnonKey)

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get burn rate color based on days remaining
 */
export function getBurnRateColor(burnRateDays: number | null): string {
  if (!burnRateDays) return 'text-gray-400'
  if (burnRateDays < 7) return 'text-red-600 font-bold'
  if (burnRateDays < 14) return 'text-orange-600 font-semibold'
  if (burnRateDays < 30) return 'text-yellow-600'
  return 'text-green-600'
}

/**
 * Get burn rate background color based on days remaining
 */
export function getBurnRateBgColor(burnRateDays: number | null): string {
  if (!burnRateDays) return 'bg-gray-100'
  if (burnRateDays < 7) return 'bg-red-50'
  if (burnRateDays < 14) return 'bg-orange-50'
  if (burnRateDays < 30) return 'bg-yellow-50'
  return 'bg-green-50'
}

/**
 * Get severity badge color
 */
export function getSeverityColor(severity: Alert['severity'] | Shortage['impact_severity']): string {
  switch (severity) {
    case 'CRITICAL':
      return 'bg-red-100 text-red-800 border-red-300'
    case 'URGENT':
    case 'HIGH':
      return 'bg-orange-100 text-orange-800 border-orange-300'
    case 'WARNING':
    case 'MEDIUM':
      return 'bg-yellow-100 text-yellow-800 border-yellow-300'
    case 'INFO':
    case 'LOW':
      return 'bg-blue-100 text-blue-800 border-blue-300'
    default:
      return 'bg-gray-100 text-gray-800 border-gray-300'
  }
}

/**
 * Format number with commas
 */
export function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return '—'
  return num.toLocaleString('en-US', { maximumFractionDigits: 1 })
}

/**
 * Format date string
 */
export function formatDate(dateString: string | null): string {
  if (!dateString) return '—'
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}
