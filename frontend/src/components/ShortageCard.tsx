import { useState, useRef, useEffect } from 'react';
import { Shortage, Alert } from '@/lib/supabase';
import { formatDate } from '@/lib/supabase';
import { AlertOctagon, CheckCircle2, Globe, ExternalLink, MoreVertical, Search, ShoppingCart, Repeat } from 'lucide-react';

type ShortageCardProps = {
    shortage: Shortage;
    relatedAlert?: Alert; // Linked order recommendation if available
    onResolve: (id: string) => void;
    onReorder?: (alert: Alert) => void;
    onSwapSuppliers?: (alert: Alert) => void;
};

export function ShortageCard({ shortage, relatedAlert, onResolve, onReorder, onSwapSuppliers }: ShortageCardProps) {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const [isResolving, setIsResolving] = useState(false);

    const impactColor: Record<string, string> = {
        CRITICAL: 'border-l-red-600 bg-red-50',
        HIGH: 'border-l-orange-500 bg-orange-50',
        MEDIUM: 'border-l-yellow-500 bg-yellow-50',
        LOW: 'border-l-blue-500 bg-blue-50',
    };

    const badgeColor: Record<string, string> = {
        CRITICAL: 'bg-red-100 text-red-800 border-red-200',
        HIGH: 'bg-orange-100 text-orange-800 border-orange-200',
        MEDIUM: 'bg-yellow-100 text-yellow-800 border-yellow-200',
        LOW: 'bg-blue-100 text-blue-800 border-blue-200',
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

    const handleResolveClick = () => {
        setIsResolving(true);
        onResolve(shortage.id);
        setIsOpen(false);
    };

    const handleFindSubstitute = () => {
        console.log("Initiating substitute search for", shortage.drug_name);
        setIsOpen(false);
    };

    const handleReorderClick = () => {
        if (relatedAlert && onReorder) {
            onReorder(relatedAlert);
            setIsOpen(false);
        }
    };

    const handleSwapClick = () => {
        if (relatedAlert && onSwapSuppliers) {
            onSwapSuppliers(relatedAlert);
            setIsOpen(false);
        }
    };

    return (
        <div className={`p-4 rounded-lg shadow-sm border-l-4 ${impactColor[shortage.impact_severity || 'MEDIUM'] || 'border-l-gray-300 bg-white'} relative transition-all hover:shadow-md`}>
            <div className="flex justify-between items-start">
                <div className="flex-1 pr-4">
                    <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 rounded text-xs font-bold border capitalize flex items-center gap-1 ${badgeColor[shortage.impact_severity || 'MEDIUM']}`}>
                            <AlertOctagon size={12} />
                            {shortage.impact_severity} IMPACT
                        </span>
                        <h3 className="text-lg font-semibold text-gray-800">{shortage.drug_name}</h3>
                        {relatedAlert && (
                            <span className="px-2 py-0.5 rounded text-xs font-bold border bg-blue-100 text-blue-800 border-blue-200 flex items-center gap-1">
                                <ShoppingCart size={12} />
                                Order Ready
                            </span>
                        )}
                    </div>

                    <p className="text-sm text-gray-700 mt-2">
                        <span className="font-semibold">Reason:</span> {shortage.description || shortage.reason}
                    </p>
                    {relatedAlert && (
                        <div className="mt-2 text-sm bg-white/60 p-2 rounded border border-blue-100 text-blue-900">
                            <p className="font-semibold text-xs text-blue-700 uppercase mb-1">Recommendation</p>
                            {relatedAlert.title}: {relatedAlert.description}
                        </div>
                    )}

                    <div className="mt-3 flex flex-wrap items-center text-xs text-gray-500 gap-4">
                        <span>Reported: {formatDate(shortage.reported_date || shortage.created_at)}</span>
                        {shortage.source && (
                            <span className="flex items-center gap-1 bg-white/50 px-2 py-0.5 rounded border border-gray-100">
                                <Globe size={12} />
                                Source: {shortage.source}
                            </span>
                        )}
                        {shortage.source_url && (
                            <a
                                href={shortage.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="flex items-center gap-1 text-blue-600 hover:underline"
                            >
                                <ExternalLink size={12} />
                                View Source
                            </a>
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
                        <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg border border-gray-100 py-1 z-10 animate-in fade-in zoom-in-95 duration-100">
                            {/* Recommended Actions from Alert */}
                            {relatedAlert && (
                                <>
                                    <div className="px-4 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                                        Recommended Actions
                                    </div>
                                    <button
                                        onClick={handleReorderClick}
                                        className="w-full text-left px-4 py-2 text-sm text-blue-700 hover:bg-blue-50 flex items-center gap-2"
                                    >
                                        <ShoppingCart size={16} />
                                        Order Stock
                                    </button>
                                    <button
                                        onClick={handleSwapClick}
                                        className="w-full text-left px-4 py-2 text-sm text-blue-700 hover:bg-blue-50 flex items-center gap-2"
                                    >
                                        <Repeat size={16} />
                                        Swap Supplier
                                    </button>
                                    <div className="my-1 border-t border-gray-100"></div>
                                </>
                            )}

                            <div className="px-4 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                                Management
                            </div>
                            <button
                                onClick={handleFindSubstitute}
                                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                            >
                                <Search size={16} className="text-gray-500" />
                                Find Substitute
                            </button>

                            <button
                                onClick={handleResolveClick}
                                disabled={isResolving}
                                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2 disabled:opacity-50"
                            >
                                <CheckCircle2 size={16} className="text-green-600" />
                                {isResolving ? 'Resolving...' : 'Mark Resolved'}
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
