import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Shortage, formatDate } from '@/lib/supabase';
import { ConfirmationModal } from './ConfirmationModal';
import { ShoppingCart, RefreshCcw, CheckCircle } from 'lucide-react';

export type ActionType = 'order' | 'supplier' | 'resolve';

export interface ActionCardData {
    id: string;
    drugName: string;
    severity: 'CRITICAL' | 'URGENT' | 'WARNING' | 'INFO';
    actionType: ActionType;
    reason: string;
    details?: string;
    source?: string;
    sourceUrl?: string;
    isInternalSource?: boolean;
    createdAt: string;
    actionRequired?: boolean;
    // Original data for handlers
    originalAlert?: Alert;
    originalShortage?: Shortage;
}

interface ActionCardProps {
    data: ActionCardData;
    onAction: (data: ActionCardData) => void;
    variant?: 'default' | 'system';
}

export function ActionCard({ data, onAction, variant = 'default' }: ActionCardProps) {
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);

    const isSystem = variant === 'system';
    // If system variant, force INFO severity visually
    const currentSeverity = isSystem ? 'INFO' : data.severity;

    const severityColors: Record<string, string> = {
        CRITICAL: 'bg-red-100 text-red-800 border-red-200',
        URGENT: 'bg-orange-100 text-orange-800 border-orange-200',
        WARNING: 'bg-yellow-100 text-yellow-800 border-yellow-200',
        INFO: 'bg-blue-100 text-blue-800 border-blue-200',
    };

    const borderColors: Record<string, string> = {
        CRITICAL: 'border-l-red-500',
        URGENT: 'border-l-orange-500',
        WARNING: 'border-l-yellow-500',
        INFO: 'border-l-blue-500',
    };

    const actionConfig: Record<ActionType, { label: string; icon: JSX.Element; modalTitle: string }> = {
        order: {
            label: 'Order',
            icon: <ShoppingCart size={14} />,
            modalTitle: 'Confirm Order',
        },
        supplier: {
            label: 'Supplier',
            icon: <RefreshCcw size={14} />,
            modalTitle: 'Confirm Supplier Change',
        },
        resolve: {
            label: 'Resolve',
            icon: <CheckCircle size={14} />,
            modalTitle: 'Resolve Issue',
        },
    };

    const config = actionConfig[data.actionType];

    const handleActionClick = () => {
        setIsModalOpen(true);
    };

    const handleConfirmAction = () => {
        setIsModalOpen(false);
        setIsProcessing(true);
        setTimeout(() => {
            onAction(data);
            setIsProcessing(false);
        }, 400);
    };

    const modalDescription =
        data.actionType === 'order'
            ? `Place a restocking order for ${data.drugName}. An automated purchase order will be sent to the primary supplier.`
            : data.actionType === 'supplier'
                ? `Change the supplier for ${data.drugName}. This will switch to the recommended alternative supplier.`
                : `Mark this issue as resolved. It will be removed from the active list.`;

    return (
        <>
            <div className={`p-4 rounded-lg shadow-sm border-l-4 bg-white ${borderColors[currentSeverity]} transition-all hover:shadow-md`}>
                {/* Header Row */}
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2 flex-wrap min-w-0">
                        {/* Severity Badge */}
                        <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full border ${severityColors[currentSeverity]}`}>
                            {currentSeverity}
                        </span>
                        {/* Drug Name */}
                        <h3 className="text-base font-semibold text-gray-900 truncate">{data.drugName}</h3>
                        {/* Action Type Badge - Hide for Systems */}
                        {!isSystem && (
                            <span className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-gray-100 text-gray-700 border border-gray-200 flex items-center gap-1 uppercase">
                                {config.icon}
                                {config.label}
                            </span>
                        )}
                    </div>
                    {/* Action Button */}
                    <button
                        onClick={handleActionClick}
                        disabled={isProcessing}
                        className={`px-3 py-1.5 text-xs font-medium rounded bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1.5 transition-colors shrink-0 ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                        {isProcessing ? 'Processing...' : (
                            <>
                                {config.icon}
                                {config.label}
                            </>
                        )}
                    </button>
                </div>

                {/* Content Sections */}
                {isSystem ? (
                    // Simplified Layout for System Alerts
                    <div className="mt-2 text-sm text-gray-700">
                        {data.details || data.reason}
                    </div>
                ) : (
                    // Default Layout
                    <div className="mt-3 space-y-2">
                        {/* Reason */}
                        <div className="text-sm bg-gray-50 p-2.5 rounded border border-gray-100">
                            <p className="font-semibold text-[10px] text-gray-500 uppercase mb-1">Reason</p>
                            <p className="text-gray-700 text-sm">{data.reason}</p>
                        </div>
                        {/* Details */}
                        {data.details && (
                            <div className="text-sm bg-blue-50 p-2.5 rounded border border-blue-100">
                                <p className="font-semibold text-[10px] text-blue-600 uppercase mb-1">Details</p>
                                <p className="text-blue-900 text-sm">{data.details}</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Footer */}
                <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-500">
                    <span>{formatDate(data.createdAt)}</span>
                    {(data.source || data.isInternalSource) && (
                        <>
                            <span className="text-gray-500">•</span>
                            <span className="text-gray-500">Source: </span>
                            {data.isInternalSource ? (
                                <Link to="/drugs" className="text-blue-600 hover:underline">
                                    {data.source || 'Stock'}
                                </Link>
                            ) : (data.sourceUrl || (data.source && (data.source.startsWith('http') || data.source.startsWith('www')))) ? (
                                <a
                                    href={data.sourceUrl || (data.source?.startsWith('www') ? `https://${data.source}` : data.source)}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-blue-600 hover:underline"
                                >
                                    {data.source}
                                </a>
                            ) : (
                                <span>{data.source}</span>
                            )}
                        </>
                    )}
                </div>
            </div>

            <ConfirmationModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                onConfirm={handleConfirmAction}
                title={config.modalTitle}
                description={modalDescription}
                confirmLabel={config.label}
                isLoading={isProcessing}
            />
        </>
    );
}

// Helper to convert shortage + alert to ActionCardData
export function createActionCardData(
    shortage?: Shortage,
    alert?: Alert
): ActionCardData | null {
    if (shortage) {
        const relatedAlertType = alert?.alert_type;
        let actionType: ActionType = 'resolve';
        if (relatedAlertType === 'RESTOCK_NOW') actionType = 'order';
        else if (relatedAlertType === 'SUBSTITUTE_RECOMMENDED') actionType = 'supplier';

        const isInternal = shortage.source?.toLowerCase().includes('stock') || shortage.source?.toLowerCase().includes('inventory');

        return {
            id: shortage.id,
            drugName: shortage.drug_name,
            severity: (shortage.impact_severity as ActionCardData['severity']) || 'INFO',
            actionType,
            reason: shortage.description || shortage.reason,
            details: alert?.description,
            source: isInternal && !shortage.source ? 'Stock' : shortage.source,
            sourceUrl: shortage.source_url,
            isInternalSource: isInternal,
            createdAt: shortage.reported_date || shortage.created_at,
            originalShortage: shortage,
            originalAlert: alert,
            actionRequired: true,
        };
    }

    if (alert) {
        let actionType: ActionType = 'resolve';
        if (alert.alert_type === 'RESTOCK_NOW') actionType = 'order';
        else if (alert.alert_type === 'SUBSTITUTE_RECOMMENDED') actionType = 'supplier';

        // Determine isInternal based on source content or if no source/url is provided (implying internal)
        const isInternal = alert.source?.toLowerCase().includes('stock') || alert.source?.toLowerCase().includes('inventory') || (!alert.source && !alert.source_url);

        return {
            id: alert.id,
            drugName: alert.drug_name,
            severity: alert.severity,
            actionType,
            reason: alert.title,
            details: alert.description,
            source: alert.source,
            sourceUrl: alert.source_url,
            isInternalSource: isInternal,
            createdAt: alert.created_at,
            originalAlert: alert,
            actionRequired: alert.action_required,
        };
    }

    return null;
}

// Severity weight for sorting
export function getSeverityWeight(severity: string): number {
    const weights: Record<string, number> = {
        CRITICAL: 4,
        URGENT: 3,
        WARNING: 2,
        INFO: 1,
    };
    return weights[severity] || 0;
}
