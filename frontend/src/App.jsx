import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Activity, LayoutDashboard, Sliders, Layers, Target, ShieldCheck, User } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import IncidentView from './pages/IncidentView';
import AuditTrail from './pages/AuditTrail';
import SimulationLab from './pages/SimulationLab';
import SegmentExplorer from './pages/SegmentExplorer';
import ModelEvaluation from './pages/ModelEvaluation';

function NavLinks() {
  const location = useLocation();
  const path = location.pathname;

  const links = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/simulator', label: 'Simulation Lab', icon: Sliders },
    { to: '/segments', label: 'Segment Explorer', icon: Layers },
    { to: '/evaluation', label: 'Model Evaluation', icon: Target },
  ];

  return (
    <div className="flex gap-4 md:gap-6 text-xs md:text-sm font-medium">
      {links.map(({ to, label, icon: Icon }) => {
        const isActive = path === to;
        return (
          <Link
            key={to}
            to={to}
            className={`flex items-center gap-1.5 transition ${
              isActive ? 'text-indigo-400 font-semibold' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Icon className="w-4 h-4" /> {label}
          </Link>
        );
      })}
    </div>
  );
}

function App() {
  const [role, setRole] = useState(localStorage.getItem('declinedoctor_user_role') || 'OPERATOR');

  const handleRoleChange = (newRole) => {
    setRole(newRole);
    localStorage.setItem('declinedoctor_user_role', newRole);
    // Dispatch storage event for cross-component synchronization
    window.dispatchEvent(new Event('storage'));
  };

  return (
    <Router>
      <div className="min-h-screen bg-[#0f111a] text-slate-200 font-sans">
        {/* Navigation Bar */}
        <nav className="border-b border-slate-800 bg-[#151822] px-6 py-3.5 flex items-center justify-between sticky top-0 z-20">
          <div className="flex items-center gap-8">
            <Link to="/" className="flex items-center gap-2">
              <Activity className="text-blue-500 w-6 h-6" />
              <span className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
                DeclineDoctor
              </span>
            </Link>
            <NavLinks />
          </div>

          {/* Role Switcher & Security Indicator */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-xs">
              <User className="w-3.5 h-3.5 text-indigo-400" />
              <span className="text-slate-400">Role:</span>
              <select
                value={role}
                onChange={(e) => handleRoleChange(e.target.value)}
                className="bg-transparent text-indigo-300 font-bold focus:outline-none cursor-pointer"
              >
                <option value="ADMIN" className="bg-slate-900 text-slate-200">ADMIN</option>
                <option value="OPERATOR" className="bg-slate-900 text-slate-200">OPERATOR</option>
                <option value="ANALYST" className="bg-slate-900 text-slate-200">ANALYST</option>
                <option value="VIEWER" className="bg-slate-900 text-slate-200">VIEWER</option>
              </select>
            </div>

            <div className="hidden sm:flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-mono font-medium">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>GUARDRAILS ACTIVE</span>
            </div>
          </div>
        </nav>

        {/* Main View Area */}
        <main className="p-6 max-w-7xl mx-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/incident/:id" element={<IncidentView />} />
            <Route path="/incident/:id/audit" element={<AuditTrail />} />
            <Route path="/simulator" element={<SimulationLab />} />
            <Route path="/segments" element={<SegmentExplorer />} />
            <Route path="/evaluation" element={<ModelEvaluation />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;