import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Activity, LayoutDashboard } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import IncidentView from './pages/IncidentView';
import AuditTrail from './pages/AuditTrail'; // <-- NEW IMPORT

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-[#0f111a] text-slate-200 font-sans">
        <nav className="border-b border-slate-800 bg-[#151822] px-6 py-4 flex items-center justify-between sticky top-0 z-10">
          <div className="flex items-center gap-2">
            <Activity className="text-blue-500 w-6 h-6" />
            <span className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
              DeclineDoctor
            </span>
          </div>
          <div className="flex gap-6 text-sm font-medium">
            <Link to="/" className="flex items-center gap-2 text-slate-400 hover:text-white transition">
              <LayoutDashboard className="w-4 h-4" /> Dashboard
            </Link>
          </div>
        </nav>

        <main className="p-6 max-w-7xl mx-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/incident/:id" element={<IncidentView />} />
            <Route path="/incident/:id/audit" element={<AuditTrail />} /> {/* <-- NEW ROUTE */}
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;