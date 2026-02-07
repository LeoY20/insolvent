import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, ShieldAlert, TrendingDown, Package, Check, X, Pencil } from 'lucide-react'
import { supabase, Alert, Drug, Shortage, formatNumber, getBurnRateColor } from '../lib/supabase'
import { SummaryCard } from '../components/SummaryCard'
import { ActionCard, ActionCardData, createActionCardData, getSeverityWeight } from '../components/ActionCard'

export default function Dashboard() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [drugs, setDrugs] = useState<Drug[]>([])
  const [shortages, setShortages] = useState<Shortage[]>([])
  const [loading, setLoading] = useState(true)

  // Inline editing state
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState<string>('')

  // ... (severityWeight and impactWeight objects remain same)
  const severityWeight = {
    CRITICAL: 4,
    URGENT: 3,
    WARNING: 2,
    INFO: 1,
  }

  const impactWeight = {
    CRITICAL: 4,
    HIGH: 3,
    MEDIUM: 2,
    LOW: 1,
  }

  function sortAlerts(alertsList: Alert[]): Alert[] {
    return [...alertsList].sort((a, b) => {
      const weightA = severityWeight[a.severity] || 0
      const weightB = severityWeight[b.severity] || 0
      if (weightA !== weightB) return weightB - weightA
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })
  }

  function sortShortages(shortagesList: Shortage[]): Shortage[] {
    return [...shortagesList].sort((a, b) => {
      const weightA = impactWeight[a.impact_severity || 'MEDIUM'] || 0
      const weightB = impactWeight[b.impact_severity || 'MEDIUM'] || 0
      if (weightA !== weightB) return weightB - weightA
      return new Date(b.reported_date || b.created_at).getTime() - new Date(a.reported_date || a.created_at).getTime()
    })
  }

  useEffect(() => {
    fetchData()

    // Subscribe to realtime updates
    const alertsChannel = supabase
      .channel('alerts-channel')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'alerts' }, (payload: { new: Alert }) => {
        setAlerts((prev) => sortAlerts([payload.new as Alert, ...prev]))
      })
      .subscribe()

    const shortagesChannel = supabase
      .channel('shortages-channel')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'shortages' }, (payload: { new: Shortage }) => {
        setShortages((prev) => sortShortages([payload.new as Shortage, ...prev]))
      })
      .subscribe()

    const drugsChannel = supabase
      .channel('drugs-channel')
      .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'drugs' }, (payload: { new: Drug }) => {
        setDrugs((prev) => prev.map((d) => (d.id === payload.new.id ? (payload.new as Drug) : d)))
      })
      .subscribe()

    return () => {
      supabase.removeChannel(alertsChannel)
      supabase.removeChannel(shortagesChannel)
      supabase.removeChannel(drugsChannel)
    }
  }, [])

  async function fetchData() {
    setLoading(true)
    try {
      const [alertsRes, drugsRes, shortagesRes] = await Promise.all([
        supabase.from('alerts').select('*').eq('acknowledged', false),
        supabase.from('drugs').select('*').order('criticality_rank'),
        supabase.from('shortages').select('*').eq('resolved', false),
      ])

      if (alertsRes.data) setAlerts(sortAlerts(alertsRes.data))
      if (drugsRes.data) setDrugs(drugsRes.data)
      if (shortagesRes.data) setShortages(sortShortages(shortagesRes.data))
    } catch (error) {
      console.error("Error fetching data:", error)
    } finally {
      setLoading(false)
    }
  }

  async function handleAcknowledge(alertId: string) {
    setAlerts((prev) => prev.filter((a) => a.id !== alertId))
    const { error } = await supabase.from('alerts').update({ acknowledged: true }).eq('id', alertId)
    if (error) {
      console.error("Failed to acknowledge alert:", error)
      fetchData()
    }
  }



  async function handleUpdateStock(drugId: string) {
    const newVal = parseInt(editValue, 10)
    if (isNaN(newVal) || newVal < 0) return

    // Find drug to get usage_rate
    const drug = drugs.find(d => d.id === drugId)
    if (!drug) return

    // Calculate burn rate: stock / daily_usage
    const burn_rate = drug.usage_rate_daily > 0
      ? newVal / drug.usage_rate_daily
      : null

    // Optimistic update with calculated burn_rate
    setDrugs(prev => prev.map(d =>
      d.id === drugId
        ? { ...d, stock_quantity: newVal, burn_rate_days: burn_rate }
        : d
    ))
    setEditingId(null)

    // Update DB with stock AND burn_rate for instant backend sync
    console.log(`[UPDATE] Sending to DB: stock=${newVal}, burn_rate=${burn_rate}, drug_id=${drugId}`)
    const { data, error } = await supabase
      .from('drugs')
      .update({
        stock_quantity: newVal,
        burn_rate_days: burn_rate,
        updated_at: new Date().toISOString()
      })
      .eq('id', drugId)
      .select()

    if (error) {
      console.error("Failed to update stock:", error)
      fetchData() // Revert
    } else {
      console.log("[UPDATE] Database update successful:", data)
    }
  }

  const navigate = useNavigate();

  function handleCardAction(data: ActionCardData) {
    if (data.actionType === 'order') {
      // Navigate to Orders page for processing
      navigate('/orders');
      return;
    }

    if (data.originalShortage) {
      // Only resolve/supplier actions remain here
    } else if (data.originalAlert) {
      handleAcknowledge(data.originalAlert.id);
    }
  }

  const actionCardsData = useMemo(() => {
    return alerts
      .filter(a => {
        const actionRequiredTypes = new Set([
          'RESTOCK_NOW',
          'SUBSTITUTE_RECOMMENDED',
          'SCHEDULE_CHANGE',
          'SUPPLY_CHAIN_RISK'
        ])
        const isActionRequired = a.action_required === true || actionRequiredTypes.has(a.alert_type)
        return !a.acknowledged && isActionRequired
      })
      .map(alert => createActionCardData(undefined, alert))
      .filter((card): card is ActionCardData => card !== null)
      .sort((a, b) => getSeverityWeight(b.severity) - getSeverityWeight(a.severity));
  }, [alerts]);

  const systemAlertsData = useMemo(() => {
    return alerts.filter(a =>
      !a.acknowledged && !(
        a.action_required === true ||
        new Set([
          'RESTOCK_NOW',
          'SUBSTITUTE_RECOMMENDED',
          'SCHEDULE_CHANGE',
          'SUPPLY_CHAIN_RISK'
        ]).has(a.alert_type)
      )
    ).map(alert => createActionCardData(undefined, alert)).filter(Boolean) as ActionCardData[];
  }, [alerts]);

  const criticalAlerts = alerts.filter((a) => a.severity === 'CRITICAL' && !a.acknowledged).length
  const urgentAlerts = alerts.filter((a) => a.severity === 'URGENT' && !a.acknowledged).length
  const lowStockDrugs = drugs.filter((d) => (d.burn_rate_days ?? 999) < 14).length
  const activeShortages = shortages.length

  if (loading) {
    return <div className="text-center py-12">Loading dashboard...</div>
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800">Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <SummaryCard title="Critical Alerts" value={criticalAlerts} icon={<ShieldAlert size={24} />} colorClass="bg-red-500" />
        <SummaryCard title="Urgent Alerts" value={urgentAlerts} icon={<AlertTriangle size={24} />} colorClass="bg-orange-500" />
        <SummaryCard title="Low Stock Drugs" value={lowStockDrugs} icon={<TrendingDown size={24} />} colorClass="bg-yellow-500" />
        <SummaryCard title="Active Shortages" value={activeShortages} icon={<Package size={24} />} colorClass="bg-primary-500" />
      </div>

      <div className="grid grid-cols-1 gap-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-gray-700 flex items-center gap-2">
              <ShieldAlert className="text-primary-600" />
              Actions Needed
            </h2>
            {actionCardsData.length === 0 ? (
              <div className="text-center bg-white p-8 rounded-lg shadow-sm border border-gray-100">
                <p className="text-gray-500">No pending actions.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {actionCardsData.map((cardData) => (
                  <ActionCard
                    key={cardData.id}
                    data={cardData}
                    onAction={handleCardAction}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-gray-700 flex items-center gap-2">
              <AlertTriangle className="text-orange-500" />
              System Alerts
            </h2>
            {systemAlertsData.length === 0 ? (
              <div className="text-center bg-white p-8 rounded-lg shadow-sm border border-gray-100">
                <p className="text-gray-500">No system alerts.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {systemAlertsData.map((cardData) => (
                  <ActionCard
                    key={cardData.id}
                    data={cardData}
                    onAction={handleCardAction}
                    variant="system"
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="bg-white shadow-sm rounded-lg">
        <h2 className="text-xl font-semibold text-gray-700 p-4 border-b">Drug Inventory Status</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Rank</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Drug</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Stock</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Daily Usage</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Burn Rate</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {drugs.map((drug) => (
                <tr key={drug.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-center font-bold">{drug.criticality_rank}</td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-800">{drug.name}</td>
                  <td className="px-4 py-3 text-sm text-right text-gray-600">
                    {editingId === drug.id ? (
                      <div className="flex items-center justify-end gap-2">
                        <input
                          type="number"
                          className="w-24 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleUpdateStock(drug.id);
                            if (e.key === 'Escape') setEditingId(null);
                          }}
                        />
                        <button onClick={() => handleUpdateStock(drug.id)} className="text-green-600 hover:text-green-800 p-1 rounded hover:bg-green-50"><Check size={16} /></button>
                        <button onClick={() => setEditingId(null)} className="text-red-500 hover:text-red-700 p-1 rounded hover:bg-red-50"><X size={16} /></button>
                      </div>
                    ) : (
                      <div className="group flex items-center justify-end gap-2 cursor-pointer p-1 rounded hover:bg-gray-100 -mr-2 pr-2" onClick={() => {
                        setEditingId(drug.id);
                        setEditValue(drug.stock_quantity.toString());
                      }}>
                        <Pencil size={14} className="text-gray-400 opacity-0 group-hover:opacity-100" />
                        <span>{formatNumber(drug.stock_quantity)} {drug.unit}</span>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-gray-600">{formatNumber(drug.usage_rate_daily)}</td>
                  <td className={`px-4 py-3 text-sm text-right font-semibold ${getBurnRateColor(drug.burn_rate_days)}`}>
                    {drug.burn_rate_days ? `${formatNumber(drug.burn_rate_days)} days` : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
