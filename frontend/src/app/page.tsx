'use client';

import { useState, useEffect } from 'react';
import Navbar from '@/components/Navbar';
import Dashboard from '@/components/Dashboard';
import KnowledgeManager from '@/components/KnowledgeManager';
import ChatInterface from '@/components/ChatInterface';
import { healthApi } from '@/lib/api';

export default function Home() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'knowledge' | 'chat'>('dashboard');
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    // Check API health on component mount
    const checkHealth = async () => {
      try {
        await healthApi.check();
        setIsHealthy(true);
      } catch (error) {
        console.error('Health check failed:', error);
        setIsHealthy(false);
      }
    };
    
    checkHealth();
  }, []);

  return (
    <div className="min-h-screen">
      <Navbar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab}
        isHealthy={isHealthy}
      />
      
      <main className="container mx-auto px-4 py-6">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'knowledge' && <KnowledgeManager />}
        {activeTab === 'chat' && <ChatInterface />}
      </main>
    </div>
  );
}
