import { useEffect, useState } from 'react';
import { supabase, Alert, Order, formatDate, getSeverityColor } from '../lib/supabase';
import { Button } from '../components/ui/button';
import { Package, Truck, CheckCircle, AlertTriangle, ArrowRight } from 'lucide-react';

export default function OrdersPage() {
    const [activeTab, setActiveTab] = useState<'alerts' | 'tracking'>('alerts');
    const [alerts, setAlerts] = useState<Alert[]>([]);
    const [orders, setOrders] = useState<Order[]>([]);
    const [loading, setLoading] = useState(true);
    const [processingId, setProcessingId] = useState<string | null>(null);

    useEffect(() => {
        fetchData();
    }, [activeTab]);

    async function fetchData() {
        setLoading(true);
        if (activeTab === 'alerts') {
            // Fetch unacknowledged alerts that need restocking
            const { data } = await supabase
                .from('alerts')
                .select('*')
                .eq('alert_type', 'RESTOCK_NOW')
                .eq('acknowledged', false)
                .order('created_at', { ascending: false });
            if (data) setAlerts(data);
        } else {
            // Fetch orders
            const { data } = await supabase
                .from('orders')
                .select(`
          *,
          drug:drugs(name),
          supplier:suppliers(name)
        `)
                .order('created_at', { ascending: false });
            if (data) setOrders(data);
        }
        setLoading(false);
    }

    async function createOrder(alert: Alert) {
        if (!alert.drug_id) return;
        setProcessingId(alert.id);

        // 1. Create the order
        const { error: orderError } = await supabase.from('orders').insert({
            drug_id: alert.drug_id,
            alert_id: alert.id,
            quantity: 100, // Default quantity, could be dynamic
            status: 'PENDING',
            notes: `Triggered by alert: ${alert.title}`
        });

        if (orderError) {
            console.error('Error creating order:', orderError);
            window.alert('Failed to create order');
            setProcessingId(null);
            return;
        }

        // 2. Acknowledge the alert so it disappears from the list
        await supabase.from('alerts').update({ acknowledged: true }).eq('id', alert.id);

        // 3. Switch tab to tracking
        setProcessingId(null);
        setActiveTab('tracking');
    }

    async function confirmOrder(orderId: string) {
        setProcessingId(orderId);
        const { error } = await supabase
            .from('orders')
            .update({ status: 'CONFIRMED' })
            .eq('id', orderId);

        if (error) {
            console.error('Error confirming order:', error);
        } else {
            fetchData();
        }
        setProcessingId(null);
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold text-gray-800">Order Management</h1>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-200">
                <nav className="-mb-px flex space-x-8">
                    <button
                        onClick={() => setActiveTab('alerts')}
                        className={`${activeTab === 'alerts'
                            ? 'border-primary-500 text-primary-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
                    >
                        <AlertTriangle className="w-4 h-4 mr-2" />
                        Action Required
                        {alerts.length > 0 && (
                            <span className="ml-2 bg-red-100 text-red-600 py-0.5 px-2 rounded-full text-xs">
                                {alerts.length}
                            </span>
                        )}
                    </button>
                    <button
                        onClick={() => setActiveTab('tracking')}
                        className={`${activeTab === 'tracking'
                            ? 'border-primary-500 text-primary-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
                    >
                        <Package className="w-4 h-4 mr-2" />
                        Order Tracking
                    </button>
                </nav>
            </div>

            {loading ? (
                <div className="text-center py-12">Loading...</div>
            ) : activeTab === 'alerts' ? (
                <div className="space-y-4">
                    {alerts.length === 0 ? (
                        <div className="text-center py-12 bg-white rounded-lg border border-dashed border-gray-300">
                            <CheckCircle className="mx-auto h-12 w-12 text-green-400" />
                            <h3 className="mt-2 text-sm font-medium text-gray-900">All caught up</h3>
                            <p className="mt-1 text-sm text-gray-500">No urgent restock alerts requiring action.</p>
                        </div>
                    ) : (
                        alerts.map((alert) => (
                            <div key={alert.id} className="bg-white shadow-sm rounded-lg p-6 border-l-4 border-red-500 flex items-center justify-between">
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="text-sm font-bold text-gray-900">{alert.drug_name}</span>
                                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${getSeverityColor(alert.severity)}`}>
                                            {alert.severity}
                                        </span>
                                    </div>
                                    <p className="text-gray-600 text-sm">{alert.description}</p>
                                    <p className="text-xs text-gray-400 mt-2">Detected: {formatDate(alert.created_at)}</p>
                                </div>
                                <Button
                                    onClick={() => createOrder(alert)}
                                    disabled={processingId === alert.id}
                                    className="bg-primary-600 hover:bg-primary-700"
                                >
                                    {processingId === alert.id ? 'Creating...' : 'Create Order'}
                                    <ArrowRight className="ml-2 h-4 w-4" />
                                </Button>
                            </div>
                        ))
                    )}
                </div>
            ) : (
                <div className="bg-white shadow-sm rounded-lg overflow-hidden">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Order ID</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Drug</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Supplier</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {orders.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                                        No active orders found.
                                    </td>
                                </tr>
                            ) : (
                                orders.map((order) => (
                                    <tr key={order.id}>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                            #{order.id.slice(0, 8)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                            {/* @ts-ignore: joined data */}
                                            {order.drug?.name || 'Unknown Drug'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                        ${order.status === 'PENDING' ? 'bg-yellow-100 text-yellow-800' :
                                                    order.status === 'CONFIRMED' ? 'bg-blue-100 text-blue-800' :
                                                        order.status === 'PLACED' ? 'bg-green-100 text-green-800' :
                                                            'bg-gray-100 text-gray-800'}`}>
                                                {order.status}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                            {/* @ts-ignore: joined data */}
                                            {order.supplier?.name || (
                                                order.status === 'CONFIRMED' ? <span className="text-blue-500 animate-pulse">Finding Supplier...</span> : '-'
                                            )}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                            {formatDate(order.created_at)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                            {order.status === 'PENDING' && (
                                                <Button
                                                    size="sm"
                                                    onClick={() => confirmOrder(order.id)}
                                                    disabled={processingId === order.id}
                                                    className="bg-green-600 hover:bg-green-700 text-white"
                                                >
                                                    {processingId === order.id ? 'Confirming...' : 'Confirm'}
                                                </Button>
                                            )}
                                            {order.status === 'PLACED' && (
                                                <div className="flex items-center justify-end text-green-600 gap-1">
                                                    <Truck className="w-4 h-4" />
                                                    <span>Shipped</span>
                                                </div>
                                            )}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
