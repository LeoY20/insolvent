import { useState, useRef, useEffect } from 'react';
import { Alert, Evidence } from '@/lib/supabase';
import { SeverityBadge } from './SeverityBadge';
import { formatDate } from '@/lib/supabase';
import { MoreVertical, CheckCircle, RefreshCcw, ArrowRightLeft, ChevronDown, ChevronUp, ExternalLink, Database, Newspaper, FileText, Calendar } from 'lucide-react';

type AlertCardProps = {
  alert: Alert;
  onAcknowledge: (id: string) => void;
  onReorder: (alert: Alert) => void;
  onSwapSuppliers: (alert: Alert) => void;
};

function SourceIcon({ type }: { type: Evidence['source_type'] }) {
  switch (type) {
    case 'INVENTORY':
      return <Database size={14} className="text-blue-600" />;
    case 'FDA':
      return <FileText size={14} className="text-green-600" />;
    case 'NEWS':
      return <Newspaper size={14} className="text-purple-600" />;
    case 'SURGERY_SCHEDULE':
      return <Calendar size={14} className="text-orange-600" />;
    default:
      return <Database size={14} className="text-gray-600" />;
  }
}

function SourceTypeBadge({ type }: { type: Evidence['source_type'] }) {
  const colors: Record<string, string> = {
    INVENTORY: 'bg-blue-100 text-blue-800',
    FDA: 'bg-green-100 text-green-800',
    NEWS: 'bg-purple-100 text-purple-800',
    SURGERY_SCHEDULE: 'bg-orange-100 text-orange-800',
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${colors[type] || 'bg-gray-100 text-gray-800'}`}>
      <SourceIcon type={type} />
      {type}
    </span>
  );
}

export function AlertCard({ alert, onAcknowledge, onReorder, onSwapSuppliers }: AlertCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const evidence = alert.action_payload?.evidence || [];

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
    <div className={`rounded-lg shadow-sm border-l-4 ${severityBorderColor[alert.severity] || 'border-l-gray-300 bg-white'} relative transition-all hover:shadow-md`}>
      <div className="p-4">
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
              {evidence.length > 0 && (
                <button
                  onClick={() => setShowEvidence(!showEvidence)}
                  className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 font-medium"
                >
                  {showEvidence ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  {evidence.length} source{evidence.length !== 1 ? 's' : ''}
                </button>
              )}
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

      {/* Evidence Panel */}
      {showEvidence && evidence.length > 0 && (
        <div className="border-t border-gray-200 bg-white/80 px-4 py-3">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Evidence & Sources</h4>
          <div className="space-y-2">
            {evidence.map((e, idx) => (
              <div key={idx} className="flex items-start gap-3 p-2 bg-gray-50 rounded-md">
                <SourceTypeBadge type={e.source_type} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 font-medium">{e.data_value}</p>
                  {e.description && (
                    <p className="text-xs text-gray-500 mt-0.5">{e.description}</p>
                  )}
                  {e.source_url && (
                    <a
                      href={e.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 mt-1"
                    >
                      <ExternalLink size={12} />
                      View source
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
