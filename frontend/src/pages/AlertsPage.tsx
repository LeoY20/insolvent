import { useEffect, useState, useMemo } from 'react';
import { supabase, Alert, formatDate, getSeverityColor } from '../lib/supabase';
import { Button } from '../components/ui/button';

const SEVERITY_LEVELS: Alert['severity'][] = ['CRITICAL', 'URGENT', 'WARNING', 'INFO'];
const ALERT_TYPES: Alert['alert_type'][] = ['RESTOCK_NOW', 'SHORTAGE_WARNING', 'SUBSTITUTE_RECOMMENDED', 'SCHEDULE_CHANGE', 'SUPPLY_CHAIN_RISK', 'AUTO_ORDER_PLACED'];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Filter states
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'acknowledged'>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  useEffect(() => {
    fetchAlerts();
  }, []); // Fetch all alerts once on initial load

  async function fetchAlerts() {
    setLoading(true);
    const { data } = await supabase.from('alerts').select('*').order('created_at', { ascending: false });
    if (data) setAlerts(data);
    setLoading(false);
  }

  const filteredAlerts = useMemo(() => {
    return alerts.filter(alert => {
      const statusMatch = statusFilter === 'all' || (statusFilter === 'active' && !alert.acknowledged) || (statusFilter === 'acknowledged' && alert.acknowledged);
      const severityMatch = severityFilter === 'all' || alert.severity === severityFilter;
      const typeMatch = typeFilter === 'all' || alert.alert_type === typeFilter;
      return statusMatch && severityMatch && typeMatch;
    });
  }, [alerts, statusFilter, severityFilter, typeFilter]);

  if (loading) {
    return <div className="text-center py-12">Loading alert history...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <h1 className="text-3xl font-bold text-gray-800">Alert History</h1>
        <div className="p-4 bg-white rounded-lg shadow-sm flex flex-col md:flex-row gap-4 items-center">
          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-600">Status:</span>
            <div className="flex items-center rounded-lg border p-0.5">
              {(['all', 'active', 'acknowledged'] as const).map(f => (
                <Button key={f} size="sm" variant={statusFilter === f ? 'default' : 'ghost'} onClick={() => setStatusFilter(f)} className="capitalize">{f}</Button>
              ))}
            </div>
          </div>
          {/* Severity Filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="severity-filter" className="text-sm font-medium text-gray-600">Severity:</label>
            <select id="severity-filter" value={severityFilter} onChange={e => setSeverityFilter(e.target.value)} className="h-9 px-3 rounded-md border border-gray-300 text-sm">
              <option value="all">All</option>
              {SEVERITY_LEVELS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          {/* Type Filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="type-filter" className="text-sm font-medium text-gray-600">Type:</label>
            <select id="type-filter" value={typeFilter} onChange={e => setTypeFilter(e.target.value)} className="h-9 px-3 rounded-md border border-gray-300 text-sm">
              <option value="all">All</option>
              {ALERT_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {filteredAlerts.length > 0 ? filteredAlerts.map((alert) => (
          <div key={alert.id} className="bg-white shadow-sm rounded-lg p-4 border-l-4" style={{ borderLeftColor: getSeverityColor(alert.severity).match(/border-([^-\s]+)/)?.[1] || 'gray' }}>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center flex-wrap gap-2 mb-2">
                  <span className={`px-2 py-1 rounded text-xs font-semibold border ${getSeverityColor(alert.severity)}`}>
                    {alert.severity}
                  </span>
                  <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-800">
                    {alert.alert_type.replace(/_/g, ' ')}
                  </span>
                  <span className="text-sm font-medium text-blue-600">{alert.drug_name}</span>
                </div>
                <h3 className="text-base font-semibold text-gray-800">{alert.title}</h3>
                <p className="text-sm text-gray-600 mt-1">{alert.description}</p>
              </div>
              <div className="text-right">
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${alert.acknowledged ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}`}>
                  {alert.acknowledged ? 'Acknowledged' : 'Active'}
                </span>
                <p className="text-xs text-gray-400 mt-2">{formatDate(alert.created_at)}</p>
              </div>
            </div>
          </div>
        )) : (
          <div className="text-center bg-white p-12 rounded-lg shadow-sm">
            <p className="text-gray-500">No alerts match the current filters.</p>
          </div>
        )}
      </div>
    </div>
  )
}
