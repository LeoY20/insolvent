import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { Activity, AlertTriangle, Package, Users, Bell, ShoppingCart } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import DrugsPage from './pages/DrugsPage'
import ShortagesPage from './pages/ShortagesPage'
import SuppliersPage from './pages/SuppliersPage'
import AlertsPage from './pages/AlertsPage'
import OrdersPage from './pages/OrdersPage'

function Navigation() {
  const location = useLocation()

  const navItems = [
    { path: '/', label: 'Dashboard', icon: Activity },
    { path: '/drugs', label: 'Drugs', icon: Package },
    { path: '/shortages', label: 'Shortages', icon: AlertTriangle },
    { path: '/suppliers', label: 'Suppliers', icon: Users },
    { path: '/alerts', label: 'Alerts', icon: Bell },
    { path: '/orders', label: 'Orders', icon: ShoppingCart },
  ]


  return (
    <nav className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
              <img src="/logo.png" alt="PharmaSentinel Logo" className="h-8 w-8 mr-2 rounded-lg" />
              <h1 className="text-xl font-bold text-primary-600">PharmaSentinel</h1>
            </div>
            <div className="hidden sm:ml-8 sm:flex sm:space-x-8">
              {navItems.map(({ path, label, icon: Icon }) => {
                const isActive = location.pathname === path
                return (
                  <Link
                    key={path}
                    to={path}
                    className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${isActive
                      ? 'border-primary-500 text-gray-900'
                      : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                      }`}
                  >
                    <Icon className="w-4 h-4 mr-2" />
                    {label}
                  </Link>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </nav>
  )
}

function App() {
  console.log('App component rendering');
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/drugs" element={<DrugsPage />} />
            <Route path="/shortages" element={<ShortagesPage />} />
            <Route path="/suppliers" element={<SuppliersPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/orders" element={<OrdersPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
