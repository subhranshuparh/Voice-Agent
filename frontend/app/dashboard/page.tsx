'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';

interface CallRecord {
  call_id: string;
  participant_identity: string;
  channel: string;
  status: 'successful' | 'failed';
  primary_action: string;
  failure_category: string;
  duration_seconds: number;
  started_at: string;
  ended_at: string;
}

interface AnalyticsData {
  total_calls: number;
  successful_calls: number;
  failed_calls: number;
  success_rate: number;
  failure_categories: {
    user_hungup_early: number;
    user_declined_consent: number;
    tool_or_api_error: number;
    no_action_taken: number;
    [key: string]: number;
  };
  recent_calls: CallRecord[];
}

export default function DashboardPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [channelFilter, setChannelFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [simulating, setSimulating] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<string>('');

  const fetchAnalytics = useCallback(async () => {
    try {
      const res = await fetch('/api/dashboard');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setError(null);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err: unknown) {
      console.error('Failed to load call analytics:', err);
      setError('Could not connect to database or fetch analytics.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchAnalytics();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchAnalytics]);

  const handleSimulateCall = async (
    status: 'successful' | 'failed',
    actionName?: string,
    failCategory?: string
  ) => {
    setSimulating(true);
    try {
      const res = await fetch('/api/dashboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status,
          primary_action:
            actionName || (status === 'successful' ? 'PHC Lookup' : 'No Action Completed'),
          failure_category: failCategory,
          channel: 'browser',
        }),
      });
      if (res.ok) {
        const updated = await res.json();
        setData(updated);
        setLastUpdated(new Date().toLocaleTimeString());
      }
    } catch (err) {
      console.error('Error simulating call:', err);
    } finally {
      setSimulating(false);
    }
  };

  const filteredCalls = (data?.recent_calls || []).filter((call) => {
    if (channelFilter !== 'all' && call.channel.toLowerCase() !== channelFilter.toLowerCase()) {
      return false;
    }
    if (statusFilter !== 'all' && call.status.toLowerCase() !== statusFilter.toLowerCase()) {
      return false;
    }
    return true;
  });

  const getFailureLabel = (cat: string) => {
    switch (cat) {
      case 'user_hungup_early':
        return 'User Hung Up Early';
      case 'user_declined_consent':
        return 'Consent Refused';
      case 'tool_or_api_error':
        return 'Tool / API Error';
      case 'no_action_taken':
        return 'No Action Taken';
      case 'none':
        return 'N/A (Success)';
      default:
        return cat.replace(/_/g, ' ');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 p-4 font-sans text-slate-100 md:p-8">
      {/* Top Navbar */}
      <header className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 border-b border-slate-800 pb-6 md:flex-row">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl border border-teal-500/30 bg-teal-500/10 text-xl font-bold text-teal-400">
            📊
          </div>
          <div>
            <h1 className="bg-gradient-to-r from-teal-300 via-emerald-400 to-cyan-300 bg-clip-text text-xl font-bold text-transparent md:text-2xl">
              Aarogya Mitra Call Analytics
            </h1>
            <p className="text-xs text-slate-400">
              #VoiceForBharat • Live Performance Dashboard & Outcome Tracker
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/80 p-1.5">
          <Link
            href="/"
            className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:text-slate-200"
          >
            🎙️ Voice Agent
          </Link>
          <Link
            href="/escalations"
            className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:text-slate-200"
          >
            📋 Escalations
          </Link>
          <span className="rounded-lg border border-teal-500/30 bg-teal-500/20 px-3 py-1.5 text-xs font-semibold text-teal-300">
            📊 Dashboard
          </span>
        </nav>
      </header>

      {/* Main Container */}
      <main className="mx-auto mt-6 max-w-7xl space-y-6">
        {error && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 p-4 text-xs text-rose-300">
            ⚠️ {error}
          </div>
        )}
        {/* Controls & Status Bar */}
        <div className="flex flex-col items-start justify-between gap-4 rounded-xl border border-slate-800/80 bg-slate-900/50 p-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <span className="relative flex size-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex size-3 rounded-full bg-emerald-500"></span>
            </span>
            <span className="text-xs text-slate-300">
              Live Database Feed • Last updated:{' '}
              <span className="font-mono text-teal-300">{lastUpdated || 'Loading...'}</span>
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => fetchAnalytics()}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 transition-all hover:bg-slate-700 active:scale-95"
            >
              🔄 Refresh Now
            </button>

            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${
                autoRefresh
                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                  : 'border-slate-700 bg-slate-800 text-slate-400'
              }`}
            >
              {autoRefresh ? '⏱️ Auto-Refresh (5s ON)' : '⏸️ Auto-Refresh OFF'}
            </button>

            {/* Test Simulation Triggers */}
            <div className="flex items-center gap-1.5 border-l border-slate-800 pl-2">
              <button
                disabled={simulating}
                onClick={() => handleSimulateCall('successful', 'PHC Lookup')}
                className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-md shadow-emerald-950/50 transition-all hover:bg-emerald-500 active:scale-95 disabled:opacity-50"
              >
                + Test Success Call
              </button>
              <button
                disabled={simulating}
                onClick={() =>
                  handleSimulateCall('failed', 'No Action Completed', 'user_hungup_early')
                }
                className="rounded-lg bg-rose-600/80 px-3 py-1.5 text-xs font-semibold text-white shadow-md shadow-rose-950/50 transition-all hover:bg-rose-500 active:scale-95 disabled:opacity-50"
              >
                + Test Fail Call
              </button>
            </div>
          </div>
        </div>

        {/* 3 Core Requirements + Success Rate Stat Cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Card 1: Total Calls */}
          <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/90 p-5 shadow-lg">
            <div className="absolute top-0 right-0 p-4 text-4xl opacity-15">📞</div>
            <p className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
              Total Calls
            </p>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-3xl font-extrabold text-slate-100 md:text-4xl">
                {loading ? '...' : (data?.total_calls ?? 0)}
              </span>
              <span className="text-xs text-slate-400">browser + SIP</span>
            </div>
            <p className="mt-2 text-[11px] text-slate-500">Recorded call sessions in SQLite</p>
          </div>

          {/* Card 2: Successful Calls */}
          <div className="relative overflow-hidden rounded-2xl border border-emerald-500/30 bg-slate-900/90 bg-gradient-to-b from-emerald-950/20 to-slate-900/90 p-5 shadow-lg">
            <div className="absolute top-0 right-0 p-4 text-4xl opacity-20">✅</div>
            <p className="text-xs font-semibold tracking-wider text-emerald-400 uppercase">
              Successful Calls
            </p>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-3xl font-extrabold text-emerald-300 md:text-4xl">
                {loading ? '...' : (data?.successful_calls ?? 0)}
              </span>
              <span className="text-xs font-medium text-emerald-400/80">completed task</span>
            </div>
            <p className="mt-2 text-[11px] text-emerald-400/60">
              PHC, Scheme, Escalation, or Reminder
            </p>
          </div>

          {/* Card 3: Failed Calls */}
          <div className="relative overflow-hidden rounded-2xl border border-rose-500/30 bg-slate-900/90 bg-gradient-to-b from-rose-950/20 to-slate-900/90 p-5 shadow-lg">
            <div className="absolute top-0 right-0 p-4 text-4xl opacity-20">❌</div>
            <p className="text-xs font-semibold tracking-wider text-rose-400 uppercase">
              Failed Calls
            </p>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-3xl font-extrabold text-rose-300 md:text-4xl">
                {loading ? '...' : (data?.failed_calls ?? 0)}
              </span>
              <span className="text-xs font-medium text-rose-400/80">incomplete / early end</span>
            </div>
            <p className="mt-2 text-[11px] text-rose-400/60">No task completed before exit</p>
          </div>

          {/* Card 4: Success Rate */}
          <div className="relative overflow-hidden rounded-2xl border border-teal-500/30 bg-slate-900/90 bg-gradient-to-b from-teal-950/20 to-slate-900/90 p-5 shadow-lg">
            <div className="absolute top-0 right-0 p-4 text-4xl opacity-20">📈</div>
            <p className="text-xs font-semibold tracking-wider text-teal-400 uppercase">
              Success Rate
            </p>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-3xl font-extrabold text-teal-300 md:text-4xl">
                {loading ? '...' : `${data?.success_rate ?? 0}%`}
              </span>
            </div>
            {/* Visual Mini Progress Bar */}
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(0, data?.success_rate || 0))}%` }}
              />
            </div>
          </div>
        </div>

        {/* Privacy Guardrail Banner (Step 6 Compliance) */}
        <div className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-950/30 p-4 text-xs text-amber-200/90">
          <span className="text-base">🛡️</span>
          <div>
            <span className="font-semibold text-amber-300">Caller Privacy Guardrail Active: </span>
            This dashboard displays only aggregated call metadata and primary task outcomes.
            Passwords, OTPs, PINs, account numbers, medical diagnosis text, and raw transcripts are
            strictly scrubbed to ensure caller confidentiality.
          </div>
        </div>

        {/* Advanced: Failure Types & Breakdown */}
        <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-200">
            <span>🏷️</span> Failure Reason Categories
          </h2>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(
              data?.failure_categories || {
                user_hungup_early: 0,
                user_declined_consent: 0,
                tool_or_api_error: 0,
                no_action_taken: 0,
              }
            ).map(([cat, count]) => (
              <div
                key={cat}
                className="flex items-center justify-between rounded-xl border border-slate-800/80 bg-slate-950/60 p-3.5"
              >
                <div>
                  <p className="text-xs font-medium text-slate-300">{getFailureLabel(cat)}</p>
                  <p className="mt-0.5 font-mono text-[10px] text-slate-500">{cat}</p>
                </div>
                <span className="rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1 font-mono text-lg font-bold text-slate-200">
                  {count}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Call History Table (Step 3 & Advanced Filters) */}
        <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/80 shadow-xl">
          {/* Table Header & Controls */}
          <div className="flex flex-col items-start justify-between gap-4 border-b border-slate-800 p-4 md:flex-row md:items-center md:p-5">
            <div>
              <h2 className="flex items-center gap-2 text-base font-bold text-slate-100">
                <span>📜</span> Call Outcome History
              </h2>
              <p className="text-xs text-slate-400">
                Real-time log of recent browser and SIP call completions
              </p>
            </div>

            {/* Filter Dropdowns */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-1.5 text-xs text-slate-400">
                <span>Channel:</span>
                <select
                  value={channelFilter}
                  onChange={(e) => setChannelFilter(e.target.value)}
                  className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-200 outline-none focus:border-teal-500"
                >
                  <option value="all">All Channels</option>
                  <option value="browser">Browser 🌐</option>
                  <option value="sip">SIP 📞</option>
                </select>
              </div>

              <div className="flex items-center gap-1.5 text-xs text-slate-400">
                <span>Status:</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-200 outline-none focus:border-teal-500"
                >
                  <option value="all">All Statuses</option>
                  <option value="successful">Successful Only ✅</option>
                  <option value="failed">Failed Only ❌</option>
                </select>
              </div>
            </div>
          </div>

          {/* Table Content */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="border-b border-slate-800 bg-slate-950/80 text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
                <tr>
                  <th className="px-4 py-3">Call ID / Time</th>
                  <th className="px-4 py-3">Channel</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Primary Objective Achieved</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3">Failure Category</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500">
                      Loading call logs from database...
                    </td>
                  </tr>
                ) : filteredCalls.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500">
                      No matching call records found. Click &quot;+ Test Success Call&quot; to
                      simulate one!
                    </td>
                  </tr>
                ) : (
                  filteredCalls.map((call) => {
                    const isSuccess = call.status === 'successful';
                    return (
                      <tr key={call.call_id} className="transition-colors hover:bg-slate-800/40">
                        {/* Call ID / Timestamp */}
                        <td className="px-4 py-3.5">
                          <div className="max-w-[140px] truncate font-mono font-semibold text-slate-200">
                            {call.call_id}
                          </div>
                          <div className="mt-0.5 text-[10px] text-slate-400">
                            {call.started_at
                              ? new Date(call.started_at).toLocaleString()
                              : 'Just now'}
                          </div>
                        </td>

                        {/* Channel */}
                        <td className="px-4 py-3.5">
                          <span className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-800 px-2.5 py-1 font-medium text-slate-300">
                            {call.channel.toLowerCase() === 'sip' ? '📞 SIP' : '🌐 Browser'}
                          </span>
                        </td>

                        {/* Duration */}
                        <td className="px-4 py-3.5 font-mono text-slate-300">
                          {call.duration_seconds}s
                        </td>

                        {/* Primary Action */}
                        <td className="px-4 py-3.5">
                          <span
                            className={`font-medium ${
                              isSuccess ? 'text-emerald-300' : 'text-slate-400'
                            }`}
                          >
                            {call.primary_action || 'No Action Completed'}
                          </span>
                        </td>

                        {/* Status Badge */}
                        <td className="px-4 py-3.5 text-center">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-[11px] font-bold ${
                              isSuccess
                                ? 'border border-emerald-500/40 bg-emerald-500/20 text-emerald-300'
                                : 'border border-rose-500/40 bg-rose-500/20 text-rose-300'
                            }`}
                          >
                            {isSuccess ? '✅ Successful' : '❌ Failed'}
                          </span>
                        </td>

                        {/* Failure Category */}
                        <td className="px-4 py-3.5">
                          <span className="text-[11px] text-slate-400">
                            {getFailureLabel(call.failure_category)}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
