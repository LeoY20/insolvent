import { getSeverityColor } from '@/lib/supabase';
import { Alert } from '@/lib/supabase';

type SeverityBadgeProps = {
  severity: Alert['severity'];
};

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  return (
    <span
      className={`px-2 py-1 text-xs font-semibold rounded-full border ${getSeverityColor(severity)}`}
    >
      {severity}
    </span>
  );
}
