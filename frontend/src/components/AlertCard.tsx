import { Alert } from '@/lib/supabase';
import { SeverityBadge } from './SeverityBadge';
import { formatDate } from '@/lib/supabase';
import { Button } from './ui/button'; // Assuming a Button component exists or will be created

type AlertCardProps = {
  alert: Alert;
  onAcknowledge: (id: string) => void;
};

export function AlertCard({ alert, onAcknowledge }: AlertCardProps) {
  const severityBorderColor = {
    CRITICAL: 'border-red-500',
    URGENT: 'border-orange-500',
    WARNING: 'border-yellow-500',
    INFO: 'border-blue-500',
  };

  return (
    <div className={`bg-white p-4 rounded-lg shadow-sm border-l-4 ${severityBorderColor[alert.severity]}`}>
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <SeverityBadge severity={alert.severity} />
            <h3 className="text-lg font-semibold text-gray-800">{alert.title}</h3>
          </div>
          <p className="text-sm text-gray-600">{alert.description}</p>
        </div>
        <div className="text-right">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onAcknowledge(alert.id)}
            >
              Acknowledge
            </Button>
            <p className="text-xs text-gray-400 mt-2">{formatDate(alert.created_at)}</p>
        </div>
      </div>
    </div>
  );
}
