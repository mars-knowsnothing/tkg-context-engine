'use client';

import { Database, MessageCircle, BarChart3, Settings, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavbarProps {
  activeTab: 'dashboard' | 'knowledge' | 'chat';
  setActiveTab: (tab: 'dashboard' | 'knowledge' | 'chat') => void;
  isHealthy: boolean | null;
}

const Navbar = ({ activeTab, setActiveTab, isHealthy }: NavbarProps) => {
  const navItems = [
    {
      id: 'dashboard' as const,
      label: 'Dashboard',
      icon: BarChart3,
      description: 'Overview & Analytics'
    },
    {
      id: 'knowledge' as const,
      label: 'Knowledge',
      icon: Database,
      description: 'Manage Knowledge Graph'
    },
    {
      id: 'chat' as const,
      label: 'Chat',
      icon: MessageCircle,
      description: 'Interactive Query Interface'
    }
  ];

  return (
    <nav className="glass border-b border-white/10 backdrop-blur-md">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-blue-500 to-cyan-400 flex items-center justify-center glow">
              <Database className="w-6 h-6 text-white" />
            </div>
            <div className="hidden sm:block">
              <h1 className="text-xl font-bold text-white terminal-text">
                TKG Context Engine
              </h1>
              <p className="text-xs text-gray-400">
                Time-aware Knowledge Graph
              </p>
            </div>
          </div>

          {/* Navigation Items */}
          <div className="flex space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={cn(
                    "flex items-center space-x-2 px-4 py-2 rounded-lg transition-all duration-200",
                    "hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-blue-400/50",
                    isActive
                      ? "bg-white/15 text-white glow"
                      : "text-gray-300 hover:text-white"
                  )}
                  title={item.description}
                >
                  <Icon className="w-5 h-5" />
                  <span className="hidden md:inline font-medium">
                    {item.label}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Status Indicator */}
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-gray-400" />
              <div className="flex items-center space-x-1">
                <div
                  className={cn(
                    "w-2 h-2 rounded-full transition-colors duration-300",
                    isHealthy === true
                      ? "bg-green-400 shadow-[0_0_10px_rgba(34,197,94,0.5)]"
                      : isHealthy === false
                      ? "bg-red-400 shadow-[0_0_10px_rgba(239,68,68,0.5)]"
                      : "bg-yellow-400 animate-pulse shadow-[0_0_10px_rgba(234,179,8,0.5)]"
                  )}
                />
                <span className="text-xs text-gray-400 hidden sm:inline">
                  {isHealthy === true
                    ? "Connected"
                    : isHealthy === false
                    ? "Disconnected"
                    : "Connecting..."}
                </span>
              </div>
            </div>
            
            <button
              className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors duration-200"
              title="Settings"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;