import { useEffect, useState, useMemo } from 'react';
import { supabase, Supplier, formatNumber } from '../lib/supabase';
import { Input } from '../components/ui/input'; // Assuming a generic Input component
import { Button } from '../components/ui/button';

type FilterType = 'all' | 'vendor' | 'hospital';

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [drugNameFilter, setDrugNameFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState<FilterType>('all');

  useEffect(() => {
    fetchSuppliers();
  }, []);

  async function fetchSuppliers() {
    setLoading(true);
    const { data } = await supabase.from('suppliers').select('*').eq('active', true).order('name');
    if (data) setSuppliers(data);
    setLoading(false);
  }

  const filteredSuppliers = useMemo(() => {
    return suppliers.filter(supplier => {
      const drugMatch = drugNameFilter.trim() === '' || supplier.drug_name.toLowerCase().includes(drugNameFilter.trim().toLowerCase());
      const typeMatch = typeFilter === 'all' || (typeFilter === 'hospital' && supplier.is_nearby_hospital) || (typeFilter === 'vendor' && !supplier.is_nearby_hospital);
      return drugMatch && typeMatch;
    });
  }, [suppliers, drugNameFilter, typeFilter]);

  if (loading) {
    return <div className="text-center py-12">Loading suppliers...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:justify-between md:items-center gap-4">
        <h1 className="text-3xl font-bold text-gray-800">Suppliers</h1>
        <div className="flex items-center gap-2">
          <Input 
            placeholder="Filter by drug name..."
            value={drugNameFilter}
            onChange={(e) => setDrugNameFilter(e.target.value)}
            className="w-48"
          />
          <div className="flex items-center rounded-lg border p-0.5">
            {(['all', 'vendor', 'hospital'] as FilterType[]).map(filter => (
              <Button
                key={filter}
                variant={typeFilter === filter ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setTypeFilter(filter)}
                className={`capitalize ${typeFilter === filter ? 'bg-blue-600 text-white' : 'text-gray-600'}`}
              >
                {filter}
              </Button>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white shadow-sm rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Drug</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Location</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Price/Unit</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Lead Time</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Reliability</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredSuppliers.map((supplier) => (
              <tr key={supplier.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm font-medium text-gray-800">{supplier.name}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{supplier.drug_name}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{supplier.location || 'N/A'}</td>
                <td className="px-4 py-3 text-sm text-right text-gray-600">${formatNumber(supplier.price_per_unit)}</td>
                <td className="px-4 py-3 text-sm text-right text-gray-600">{supplier.lead_time_days ?? 'N/A'} days</td>
                <td className="px-4 py-3 text-sm text-right text-gray-600">{formatNumber(supplier.reliability_score * 100)}%</td>
                <td className="px-4 py-3 text-sm">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${supplier.is_nearby_hospital ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}`}>
                    {supplier.is_nearby_hospital ? 'Hospital' : 'Vendor'}
                  </span>
                </td>
              </tr>
            ))}
            {filteredSuppliers.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center py-12 text-gray-500">
                  No suppliers match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
