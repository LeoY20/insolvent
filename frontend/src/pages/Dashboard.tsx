import { useEffect, useState } from 'react'
import { AlertTriangle, ShieldAlert, TrendingDown, Package } from 'lucide-react'
import { supabase, Alert, Drug, Shortage, formatNumber, getBurnRateColor } from '../lib/supabase'
import { SummaryCard } from '../components/SummaryCard'
import { AlertCard } from '../components/AlertCard'

export default function Dashboard() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [drugs, setDrugs] = useState<Drug[]>([])
  const [shortages, setShortages] = useState<Shortage[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()

    // Subscribe to realtime updates
    const alertsChannel = supabase
      .channel('alerts-channel')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'alerts' }, (payload: { new: Alert }) => {
        setAlerts((prev) => [payload.new as Alert, ...prev])
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
      supabase.removeChannel(drugsChannel)
    }
  }, [])

  async function fetchData() {
    setLoading(true)
    try {
      const [alertsRes, drugsRes, shortagesRes] = await Promise.all([
        supabase.from('alerts').select('*').eq('acknowledged', false).order('created_at', { ascending: false }),
        supabase.from('drugs').select('*').order('criticality_rank'),
        supabase.from('shortages').select('*').eq('resolved', false),
      ])

      if (alertsRes.data) setAlerts(alertsRes.data)
      if (drugsRes.data) setDrugs(drugsRes.data)
      if (shortagesRes.data) setShortages(shortagesRes.data)
    } catch (error) {
      console.error("Error fetching data:", error)
    } finally {
      setLoading(false)
    }
  }

  async function handleAcknowledge(alertId: string) {
    // Optimistically update UI
    setAlerts((prev) => prev.filter((a) => a.id !== alertId))
    
    const { error } = await supabase.from('alerts').update({ acknowledged: true }).eq('id', alertId)
    if (error) {
      console.error("Failed to acknowledge alert:", error)
      // Revert UI if update fails
      fetchData() 
    }
  }

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
      
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <SummaryCard title="Critical Alerts" value={criticalAlerts} icon={<ShieldAlert size={24} />} colorClass="bg-red-500" />
        <SummaryCard title="Urgent Alerts" value={urgentAlerts} icon={<AlertTriangle size={24} />} colorClass="bg-orange-500" />
        <SummaryCard title="Low Stock Drugs" value={lowStockDrugs} icon={<TrendingDown size={24} />} colorClass="bg-yellow-500" />
        <SummaryCard title="Active Shortages" value={activeShortages} icon={<Package size={24} />} colorClass="bg-blue-500" />
      </div>

      {/* Active Alerts */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-700">Active Alerts</h2>
        {alerts.filter(a => !a.acknowledged).length === 0 ? (
          <div className="text-center bg-white p-8 rounded-lg shadow-sm">
            <p className="text-gray-500">No active alerts. System is stable.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.filter(a => !a.acknowledged).map((alert) => (
              <AlertCard key={alert.id} alert={alert} onAcknowledge={handleAcknowledge} />
            ))}
          </div>
        )}
      </div>

      {/* Drug Inventory Table */}
      <div className="bg-white shadow-sm rounded-lg">
        <h2 className="text-xl font-semibold text-gray-700 p-4 border-b">Drug Inventory Status</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rank</th>
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
                    {formatNumber(drug.stock_quantity)} {drug.unit}
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
