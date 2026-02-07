import { useState, useRef, useEffect } from 'react';
import { Alert } from '@/lib/supabase';
import { SeverityBadge } from './SeverityBadge';
import { formatDate } from '@/lib/supabase';
import { MoreVertical, CheckCircle, RefreshCcw, ArrowRightLeft } from 'lucide-react';

type AlertCardProps = {
  alert: Alert;
  onAcknowledge: (id: string) => void;
  onReorder: (alert: Alert) => void;
  onSwapSuppliers: (alert: Alert) => void;
};

export function AlertCard({ alert, onAcknowledge, onReorder, onSwapSuppliers }: AlertCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const severityBorderColor: Record<string, string> = {
    CRITICAL: 'border-l-red-500 bg-red-50',
    URGENT: 'border-l-orange-500 bg-orange-50',
    WARNING: 'border-l-yellow-500 bg-yellow-50',
    INFO: 'border-l-blue-500 bg-blue-50',
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  return (
    <div className={`p-4 rounded-lg shadow-sm border-l-4 ${severityBorderColor[alert.severity] || 'border-l-gray-300 bg-white'} relative transition-all hover:shadow-md`}>
      <div className="flex justify-between items-start">
        <div className="flex-1 pr-4">
          <div className="flex items-center gap-2 mb-1">
            <SeverityBadge severity={alert.severity} />
            <h3 className="text-lg font-semibold text-gray-800">{alert.title}</h3>
          </div>
          <p className="text-sm text-gray-700 mt-1">{alert.description}</p>
          <div className="mt-3 flex items-center text-xs text-gray-500 gap-4">
            <span>{formatDate(alert.created_at)}</span>
            {alert.drug_name && <span className="font-medium bg-white/50 px-2 py-0.5 rounded">Drug: {alert.drug_name}</span>}
          </div>
        </div>

        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="p-2 hover:bg-black/5 rounded-full transition-colors text-gray-500 hover:text-gray-700"
            aria-label="Options"
          >
            <MoreVertical size={20} />
          </button>

          {isOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg border border-gray-100 py-1 z-10 animate-in fade-in zoom-in-95 duration-100">
              <button
                onClick={() => { onAcknowledge(alert.id); setIsOpen(false); }}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
              >
                <CheckCircle size={16} className="text-green-600" />
                Acknowledge
              </button>

              <button
                onClick={() => { onReorder(alert); setIsOpen(false); }}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
              >
                <RefreshCcw size={16} className="text-blue-600" />
                Reorder
              </button>

              <button
                onClick={() => { onSwapSuppliers(alert); setIsOpen(false); }}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
              >
                <ArrowRightLeft size={16} className="text-orange-600" />
                Swap Suppliers
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
