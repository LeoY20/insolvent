import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { supabase, Drug, Substitute, Shortage, Supplier, formatNumber, getBurnRateColor, getBurnRateBgColor, formatDate } from '../lib/supabase'

interface DrugWithRelations extends Drug {
  substitutes?: Substitute[]
  shortages?: Shortage[]
  suppliers?: Supplier[]
}

export default function DrugsPage() {
  const [drugs, setDrugs] = useState<DrugWithRelations[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedDrugId, setExpandedDrugId] = useState<string | null>(null)

  useEffect(() => {
    fetchDrugs()
  }, [])

  function normalizeName(value: string | null | undefined) {
    if (!value) return ''
    return value.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
  }

  async function fetchDrugs() {
    const { data: drugsData } = await supabase.from('drugs').select('*').order('criticality_rank')

    if (drugsData) {
      // Fetch related data for all drugs
      const [substitutesRes, shortagesRes, suppliersRes] = await Promise.all([
        supabase.from('substitutes').select('*'),
        supabase.from('shortages').select('*').eq('resolved', false),
        supabase.from('suppliers').select('*').eq('active', true)
      ])

      const substitutes = substitutesRes.data || []
      const shortages = shortagesRes.data || []
      const suppliers = suppliersRes.data || []

      // Map related data to each drug
      const drugsWithRelations: DrugWithRelations[] = drugsData.map((drug: Drug) => ({
        ...drug,
        substitutes: substitutes.filter((s: Substitute) => s.drug_name === drug.name),
        shortages: shortages.filter((s: Shortage) => {
          const drugKey = normalizeName(drug.name)
          const shortageKey = normalizeName(s.drug_name)
          return drugKey !== '' && drugKey === shortageKey
        }),
        suppliers: suppliers.filter((s: Supplier) => s.drug_name === drug.name)
      }))

      setDrugs(drugsWithRelations)
    }
    setLoading(false)
  }

  function toggleExpand(drugId: string) {
    setExpandedDrugId(expandedDrugId === drugId ? null : drugId)
  }

  function generateProjectionData(drug: Drug) {
    const data = []
    const currentStock = drug.stock_quantity
    const dailyUsage = drug.predicted_usage_rate || drug.usage_rate_daily

    for (let day = 0; day <= 30; day++) {
      const projectedStock = Math.max(0, currentStock - (dailyUsage * day))
      data.push({
        day: `Day ${day}`,
        stock: Math.round(projectedStock * 10) / 10,
        reorderThreshold: drug.reorder_threshold_days ? dailyUsage * drug.reorder_threshold_days : 0,
        criticalLevel: dailyUsage * 7
      })
    }
    return data
  }

  if (loading) return <div className="text-center py-12">Loading...</div>

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Drug Inventory</h1>

      <div className="bg-white shadow-sm rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="w-10 px-3 py-3"></th>
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rank</th>
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Drug Name</th>
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Stock</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Daily Usage</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Pred. Usage</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Burn Rate</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Pred. Burn</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {drugs.map((drug) => (
              <>
                <tr
                  key={drug.id}
                  className={`hover:bg-gray-50 cursor-pointer ${getBurnRateBgColor(drug.predicted_burn_rate_days ?? drug.burn_rate_days)}`}
                  onClick={() => toggleExpand(drug.id)}
                >
                  <td className="px-3 py-4 whitespace-nowrap">
                    {expandedDrugId === drug.id ? (
                      <ChevronDown className="w-5 h-5 text-gray-500" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-gray-500" />
                    )}
                  </td>
                  <td className="px-3 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{drug.criticality_rank}</td>
                  <td className="px-3 py-4 text-sm font-bold text-gray-900 max-w-[200px] break-words">{drug.name}</td>
                  <td className="px-3 py-4 text-sm text-gray-500 break-words">{drug.type}</td>
                  <td className="px-3 py-4 whitespace-nowrap text-sm text-right">
                    {formatNumber(drug.stock_quantity)} {drug.unit}
                  </td>
                  <td className="px-3 py-4 whitespace-nowrap text-sm text-right">{formatNumber(drug.usage_rate_daily)}</td>
                  <td className="px-3 py-4 whitespace-nowrap text-sm text-right">{formatNumber(drug.predicted_usage_rate)}</td>
                  <td className={`px-3 py-4 whitespace-nowrap text-sm text-right ${getBurnRateColor(drug.burn_rate_days)}`}>
                    {drug.burn_rate_days ? `${formatNumber(drug.burn_rate_days)} days` : '—'}
                  </td>
                  <td className={`px-3 py-4 whitespace-nowrap text-sm text-right ${getBurnRateColor(drug.predicted_burn_rate_days)}`}>
                    {drug.predicted_burn_rate_days ? `${formatNumber(drug.predicted_burn_rate_days)} days` : '—'}
                  </td>
                </tr>

                {/* Expanded Row */}
                {expandedDrugId === drug.id && (
                  <tr key={`${drug.id}-expanded`}>
                    <td colSpan={9} className="px-6 py-6 bg-gray-50">
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Stock Projection Chart */}
                        <div className="bg-white rounded-lg p-4 shadow-sm">
                          <h4 className="text-sm font-semibold text-gray-900 mb-4">30-Day Stock Projection</h4>
                          <div className="h-64">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={generateProjectionData(drug)}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="day" tick={{ fontSize: 10 }} interval={4} />
                                <YAxis tick={{ fontSize: 10 }} />
                                <Tooltip />
                                <Legend />
                                <Line
                                  type="monotone"
                                  dataKey="stock"
                                  stroke="#3b82f6"
                                  strokeWidth={2}
                                  name="Projected Stock"
                                  dot={false}
                                />
                                <Line
                                  type="monotone"
                                  dataKey="reorderThreshold"
                                  stroke="#f59e0b"
                                  strokeDasharray="5 5"
                                  name="Reorder Threshold"
                                  dot={false}
                                />
                                <Line
                                  type="monotone"
                                  dataKey="criticalLevel"
                                  stroke="#ef4444"
                                  strokeDasharray="5 5"
                                  name="Critical Level"
                                  dot={false}
                                />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        </div>

                        {/* Related Information */}
                        <div className="space-y-4">
                          {/* Substitutes */}
                          <div className="bg-white rounded-lg p-4 shadow-sm">
                            <h4 className="text-sm font-semibold text-gray-900 mb-3">
                              Substitutes ({drug.substitutes?.length || 0})
                            </h4>
                            {drug.substitutes && drug.substitutes.length > 0 ? (
                              <div className="space-y-2">
                                {drug.substitutes.map(sub => (
                                  <div key={sub.id} className="flex justify-between items-center p-2 bg-gray-50 rounded text-sm">
                                    <div>
                                      <span className="font-medium">{sub.substitute_name}</span>
                                      <span className="ml-2 text-xs text-gray-500">Rank #{sub.preference_rank}</span>
                                    </div>
                                    {sub.equivalence_notes && (
                                      <span className="text-xs text-gray-500 max-w-xs truncate">{sub.equivalence_notes}</span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-gray-500">No substitutes available</p>
                            )}
                          </div>

                          {/* Active Shortages */}
                          <div className="bg-white rounded-lg p-4 shadow-sm">
                            <h4 className="text-sm font-semibold text-gray-900 mb-3">
                              Active Shortages ({drug.shortages?.length || 0})
                            </h4>
                            {drug.shortages && drug.shortages.length > 0 ? (
                              <div className="space-y-2">
                                {drug.shortages.map(shortage => (
                                  <div key={shortage.id} className="p-2 bg-red-50 rounded text-sm">
                                    <div className="flex justify-between items-center">
                                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${shortage.impact_severity === 'CRITICAL' ? 'bg-red-100 text-red-800' :
                                        shortage.impact_severity === 'HIGH' ? 'bg-orange-100 text-orange-800' :
                                          'bg-yellow-100 text-yellow-800'
                                        }`}>
                                        {shortage.impact_severity}
                                      </span>
                                      <span className="text-xs text-gray-500">{formatDate(shortage.reported_date)}</span>
                                    </div>
                                    <p className="text-xs text-gray-600 mt-1">{shortage.description || shortage.source}</p>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-green-600">No active shortages</p>
                            )}
                          </div>

                          {/* Suppliers */}
                          <div className="bg-white rounded-lg p-4 shadow-sm">
                            <h4 className="text-sm font-semibold text-gray-900 mb-3">
                              Suppliers ({drug.suppliers?.length || 0})
                            </h4>
                            {drug.suppliers && drug.suppliers.length > 0 ? (
                              <div className="space-y-2">
                                {drug.suppliers.map(supplier => (
                                  <div key={supplier.id} className="flex justify-between items-center p-2 bg-gray-50 rounded text-sm">
                                    <div>
                                      <span className="font-medium">{supplier.name}</span>
                                      {supplier.is_nearby_hospital && (
                                        <span className="ml-2 px-1.5 py-0.5 bg-blue-100 text-blue-800 rounded text-xs">Hospital</span>
                                      )}
                                    </div>
                                    <div className="text-right text-xs text-gray-500">
                                      <div>${formatNumber(supplier.price_per_unit)}/unit</div>
                                      <div>{supplier.lead_time_days} day lead</div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-gray-500">No suppliers in database</p>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
