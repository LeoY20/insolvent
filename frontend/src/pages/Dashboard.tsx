import { useEffect, useState, useMemo } from 'react'
import { AlertTriangle, ShieldAlert, TrendingDown, Package } from 'lucide-react'
import { supabase, Alert, Drug, Shortage, formatNumber, getBurnRateColor } from '../lib/supabase'
import { SummaryCard } from '../components/SummaryCard'
import { ActionCard, ActionCardData, createActionCardData, getSeverityWeight } from '../components/ActionCard'

export default function Dashboard() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [drugs, setDrugs] = useState<Drug[]>([])
  const [shortages, setShortages] = useState<Shortage[]>([])
  const [loading, setLoading] = useState(true)

  // Severity weights for sorting
  const severityWeight = {
    CRITICAL: 4,
    URGENT: 3,
    WARNING: 2,
    INFO: 1,
  }

  // Impact weights for shortages
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
      // Sort by severity (descending), then by date (descending)
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
    // Optimistically update UI
    setAlerts((prev) => prev.filter((a) => a.id !== alertId))

    const { error } = await supabase.from('alerts').update({ acknowledged: true }).eq('id', alertId)
    if (error) {
      console.error("Failed to acknowledge alert:", error)
      // Revert UI if update fails
      fetchData()
    }
  }

  async function handleResolveShortage(shortageId: string) {
    // Optimistically update UI
    setShortages((prev) => prev.filter((s) => s.id !== shortageId))

    const { error } = await supabase.from('shortages').update({ resolved: true }).eq('id', shortageId)
    if (error) {
      console.error("Failed to resolve shortage:", error)
      fetchData()
    }
  }

  // Handler for ActionCard unified action
  function handleCardAction(data: ActionCardData) {
    if (data.originalShortage) {
      if (data.actionType === 'order' && data.originalAlert) {
        console.log("Initiating reorder for", data.drugName);
        handleAcknowledge(data.originalAlert.id);
      } else if (data.actionType === 'supplier' && data.originalAlert) {
        console.log("Initiating supplier swap for", data.drugName);
        handleAcknowledge(data.originalAlert.id);
      } else {
        handleResolveShortage(data.originalShortage.id);
      }
    } else if (data.originalAlert) {
      if (data.actionType === 'order') {
        console.log("Initiating reorder for", data.drugName);
      } else if (data.actionType === 'supplier') {
        console.log("Initiating supplier swap for", data.drugName);
      }
      handleAcknowledge(data.originalAlert.id);
    }
  }

  // Build action cards data from alerts only (ignore shortages for actions as per request)
  const actionCardsData = useMemo(() => {
    return alerts
      .filter(a => !a.acknowledged && a.action_required === true)
      .map(alert => createActionCardData(undefined, alert))
      .filter((card): card is ActionCardData => card !== null)
      .sort((a, b) => getSeverityWeight(b.severity) - getSeverityWeight(a.severity));
  }, [alerts]);

  // System alerts (non-actionable)
  const systemAlertsData = useMemo(() => {
    return alerts.filter(a =>
      !a.acknowledged &&
      !a.action_required // Capture false or undefined
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

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <SummaryCard title="Critical Alerts" value={criticalAlerts} icon={<ShieldAlert size={24} />} colorClass="bg-red-500" />
        <SummaryCard title="Urgent Alerts" value={urgentAlerts} icon={<AlertTriangle size={24} />} colorClass="bg-orange-500" />
        <SummaryCard title="Low Stock Drugs" value={lowStockDrugs} icon={<TrendingDown size={24} />} colorClass="bg-yellow-500" />
        <SummaryCard title="Active Shortages" value={activeShortages} icon={<Package size={24} />} colorClass="bg-blue-500" />
      </div>

      <div className="grid grid-cols-1 gap-6">
        {/* Detected Shortages Section with Embedded Recommendations */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Actions Needed Section */}
          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-gray-700 flex items-center gap-2">
              <ShieldAlert className="text-blue-600" />
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

          {/* System Alerts Section */}
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
