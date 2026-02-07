import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase, Shortage, formatDate, getImpactSeverityColor } from '../lib/supabase'

export default function ShortagesPage() {
  const [shortages, setShortages] = useState<Shortage[]>([])
  const [filter, setFilter] = useState<'all' | 'active' | 'resolved'>('active')

  useEffect(() => {
    fetchShortages()
  }, [filter])

  async function fetchShortages() {
    let query = supabase.from('shortages').select('*').order('reported_date', { ascending: false })

    if (filter === 'active') query = query.eq('resolved', false)
    if (filter === 'resolved') query = query.eq('resolved', true)

    const { data } = await query
    if (data) setShortages(data)
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Drug Shortages</h1>
        <div className="flex gap-2">
          {(['all', 'active', 'resolved'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg text-sm font-medium ${filter === f ? 'bg-primary-600 text-white' : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white shadow-sm rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Drug</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Severity</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reported</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {shortages.map((shortage) => (
              <tr key={shortage.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 text-sm font-medium text-gray-900">{shortage.drug_name}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{shortage.type}</td>
                <td className="px-6 py-4 text-sm text-gray-500">
                  {(() => {
                    const isInternal = shortage.source?.toLowerCase().includes('stock') || shortage.source?.toLowerCase().includes('inventory');
                    const isUrl = shortage.source_url || (shortage.source && (shortage.source.startsWith('http') || shortage.source.startsWith('www')));
                    const url = shortage.source_url || (shortage.source?.startsWith('www') ? `https://${shortage.source}` : shortage.source);

                    if (isInternal) {
                      return (
                        <Link to="/drugs" className="text-blue-600 hover:underline">
                          {shortage.source || 'Stock'}
                        </Link>
                      );
                    }
                    if (isUrl) {
                      return (
                        <a href={url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                          {shortage.source}
                        </a>
                      );
                    }
                    return shortage.source;
                  })()}
                </td>
                <td className="px-6 py-4 text-sm">
                  <span className={`px-2 py-1 rounded text-xs font-medium border ${getImpactSeverityColor(shortage.impact_severity)}`}>
                    {shortage.impact_severity}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">{formatDate(shortage.reported_date)}</td>
                <td className="px-6 py-4 text-sm">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${shortage.resolved ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {shortage.resolved ? 'Resolved' : 'Active'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
