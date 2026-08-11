'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  Clock,
  FileText,
  Filter,
  Phone,
  RefreshCw,
  Search,
  ShieldAlert,
  User,
} from 'lucide-react';

interface Escalation {
  escalation_id: string;
  caller_name: string;
  phone_or_contact: string;
  reason_type: string;
  what_happened: string;
  checked_by_agent: string;
  urgency: 'low' | 'medium' | 'high' | 'emergency';
  language: string;
  preferred_followup: string;
  status: 'open' | 'in_progress' | 'resolved';
  created_at: string;
  updated_at: string;
}

export default function EscalationDashboard() {
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const fetchEscalations = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/escalations?status=${filterStatus}`);
      const data = await res.json();
      if (data.escalations) {
        setEscalations(data.escalations);
      }
    } catch (err) {
      console.error('Failed to load escalations:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEscalations();
    const interval = setInterval(() => {
      fetchEscalations();
    }, 3000);
    return () => clearInterval(interval);
  }, [filterStatus]);

  const handleStatusChange = async (id: string, newStatus: string) => {
    try {
      const res = await fetch('/api/escalations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ escalation_id: id, new_status: newStatus }),
      });
      if (res.ok) {
        fetchEscalations();
      }
    } catch (err) {
      console.error('Failed to update status:', err);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredEscalations = escalations.filter((esc) => {
    const query = searchQuery.toLowerCase();
    return (
      esc.caller_name.toLowerCase().includes(query) ||
      esc.escalation_id.toLowerCase().includes(query) ||
      esc.what_happened.toLowerCase().includes(query) ||
      esc.reason_type.toLowerCase().includes(query)
    );
  });

  const counts = {
    total: escalations.length,
    open: escalations.filter((e) => e.status === 'open').length,
    highUrgent: escalations.filter((e) => ['high', 'emergency'].includes(e.urgency)).length,
    resolved: escalations.filter((e) => e.status === 'resolved').length,
  };

  const getUrgencyBadge = (urgency: string) => {
    switch (urgency.toLowerCase()) {
      case 'emergency':
        return 'bg-red-500/15 text-red-500 border-red-500/30 dark:bg-red-500/20 dark:text-red-400';
      case 'high':
        return 'bg-orange-500/15 text-orange-600 border-orange-500/30 dark:bg-orange-500/20 dark:text-orange-400';
      case 'medium':
        return 'bg-amber-500/15 text-amber-600 border-amber-500/30 dark:bg-amber-500/20 dark:text-amber-400';
      default:
        return 'bg-blue-500/15 text-blue-600 border-blue-500/30 dark:bg-blue-500/20 dark:text-blue-400';
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'open':
        return 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30';
      case 'in_progress':
        return 'bg-purple-500/15 text-purple-600 dark:text-purple-400 border-purple-500/30';
      case 'resolved':
        return 'bg-neutral-500/15 text-neutral-600 dark:text-neutral-400 border-neutral-500/30';
      default:
        return 'bg-neutral-500/15 text-neutral-600 border-neutral-500/30';
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 p-6 font-sans text-neutral-100 md:p-10">
      {/* Header Bar */}
      <div className="mx-auto max-w-7xl space-y-8">
        <div className="flex flex-col items-start justify-between gap-4 border-b border-neutral-800 pb-6 md:flex-row md:items-center">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <Link
                href="/"
                className="rounded-lg border border-neutral-800 bg-neutral-900 p-2 text-neutral-400 transition hover:text-white"
              >
                <ArrowLeft className="h-4 w-4" />
              </Link>
              <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-white md:text-3xl">
                <ShieldAlert className="h-7 w-7 text-teal-400" />
                Human Help Escalation Dashboard
              </h1>
            </div>
            <p className="pl-11 text-sm text-neutral-400">
              Aarogya Mitra Voice Assistant • Healthcare Supervisor Dispatch Queue (#VoiceForBharat)
            </p>
          </div>

          <button
            onClick={fetchEscalations}
            disabled={loading}
            className="flex items-center gap-2 rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-2 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin text-teal-400' : ''}`} />
            Refresh Queue
          </button>
        </div>

        {/* Metrics Overview Cards */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="space-y-1 rounded-2xl border border-neutral-800/80 bg-neutral-900/60 p-5">
            <span className="text-xs font-semibold tracking-wider text-neutral-500 uppercase">
              Total Escalations
            </span>
            <div className="text-3xl font-bold text-white">{counts.total}</div>
          </div>
          <div className="space-y-1 rounded-2xl border border-neutral-800/80 bg-neutral-900/60 p-5">
            <span className="text-xs font-semibold tracking-wider text-emerald-500 uppercase">
              Active Open
            </span>
            <div className="text-3xl font-bold text-emerald-400">{counts.open}</div>
          </div>
          <div className="space-y-1 rounded-2xl border border-neutral-800/80 bg-neutral-900/60 p-5">
            <span className="text-xs font-semibold tracking-wider text-red-500 uppercase">
              High / Emergency
            </span>
            <div className="text-3xl font-bold text-red-400">{counts.highUrgent}</div>
          </div>
          <div className="space-y-1 rounded-2xl border border-neutral-800/80 bg-neutral-900/60 p-5">
            <span className="text-xs font-semibold tracking-wider text-neutral-400 uppercase">
              Resolved
            </span>
            <div className="text-3xl font-bold text-neutral-400">{counts.resolved}</div>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="flex flex-col items-center justify-between gap-4 rounded-2xl border border-neutral-800 bg-neutral-900/40 p-3 sm:flex-row">
          <div className="flex w-full items-center gap-2 rounded-xl border border-neutral-800 bg-neutral-950 px-3 py-2 sm:w-80">
            <Search className="h-4 w-4 text-neutral-500" />
            <input
              type="text"
              placeholder="Search by caller, ID, or summary..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full border-none bg-transparent text-sm text-white placeholder-neutral-500 outline-none"
            />
          </div>

          <div className="flex w-full items-center gap-2 overflow-x-auto sm:w-auto">
            <Filter className="ml-1 h-4 w-4 text-neutral-500" />
            {['all', 'open', 'in_progress', 'resolved'].map((st) => (
              <button
                key={st}
                onClick={() => setFilterStatus(st)}
                className={`rounded-lg border px-3.5 py-1.5 text-xs font-semibold tracking-wider uppercase transition ${
                  filterStatus === st
                    ? 'border-teal-500/40 bg-teal-500/20 text-teal-400'
                    : 'border-neutral-800 bg-neutral-950 text-neutral-400 hover:bg-neutral-900'
                }`}
              >
                {st.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Escalations List */}
        {loading ? (
          <div className="space-y-3 py-20 text-center text-neutral-500">
            <RefreshCw className="mx-auto h-8 w-8 animate-spin text-teal-500" />
            <p className="text-sm">Loading escalation requests...</p>
          </div>
        ) : filteredEscalations.length === 0 ? (
          <div className="space-y-3 rounded-3xl border border-neutral-800/60 bg-neutral-900/20 py-20 text-center">
            <CheckCircle2 className="mx-auto h-12 w-12 text-teal-500/50" />
            <h3 className="text-lg font-medium text-neutral-300">No Escalations Found</h3>
            <p className="mx-auto max-w-md text-sm text-neutral-500">
              All clear! No human help requests match your current search and filter criteria.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {filteredEscalations.map((esc) => (
              <div
                key={esc.escalation_id}
                className="space-y-5 rounded-2xl border border-neutral-800 bg-neutral-900/70 p-6 transition hover:border-neutral-700"
              >
                {/* Header Row */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-neutral-800/80 pb-4">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => copyToClipboard(esc.escalation_id)}
                      className="flex items-center gap-1.5 rounded-lg border border-teal-800/50 bg-teal-950/60 px-3 py-1 font-mono text-sm font-bold text-teal-400 transition hover:bg-teal-900/50"
                      title="Click to copy Reference ID"
                    >
                      {esc.escalation_id}
                      {copiedId === esc.escalation_id ? (
                        <Check className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <FileText className="h-3.5 w-3.5 opacity-60" />
                      )}
                    </button>

                    <span
                      className={`rounded-md border px-2.5 py-1 text-xs font-bold tracking-wider uppercase ${getUrgencyBadge(
                        esc.urgency
                      )}`}
                    >
                      {esc.urgency} Urgency
                    </span>

                    <span
                      className={`rounded-md border px-2.5 py-1 text-xs font-bold tracking-wider uppercase ${getStatusBadge(
                        esc.status
                      )}`}
                    >
                      {esc.status.replace('_', ' ')}
                    </span>
                  </div>

                  <div className="flex items-center gap-1 text-xs text-neutral-500">
                    <Clock className="h-3.5 w-3.5" />
                    {new Date(esc.created_at).toLocaleString('en-IN', {
                      timeZone: 'Asia/Kolkata',
                    })}
                  </div>
                </div>

                {/* Main Content Info Grid */}
                <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                  {/* Column 1: Caller Details */}
                  <div className="space-y-2 border-r-0 border-neutral-800/80 pr-0 md:border-r md:pr-4">
                    <div className="flex items-center gap-2 text-base font-medium text-white">
                      <User className="h-4 w-4 text-teal-400" />
                      {esc.caller_name}
                    </div>
                    {esc.phone_or_contact && (
                      <div className="flex items-center gap-2 text-xs text-neutral-400">
                        <Phone className="h-3.5 w-3.5 text-neutral-500" />
                        {esc.phone_or_contact}
                      </div>
                    )}
                    <div className="space-y-1 pt-1 text-xs text-neutral-400">
                      <div>
                        <span className="text-neutral-500">Language:</span> {esc.language}
                      </div>
                      <div>
                        <span className="text-neutral-500">Preferred Follow-up:</span>{' '}
                        {esc.preferred_followup}
                      </div>
                    </div>
                  </div>

                  {/* Column 2: What Happened (Sanitized Summary) */}
                  <div className="space-y-1 md:col-span-2">
                    <span className="text-xs font-semibold tracking-wider text-neutral-400 uppercase">
                      Summary (What Happened)
                    </span>
                    <p className="rounded-xl border border-neutral-800/60 bg-neutral-950/60 p-3 text-sm text-neutral-200">
                      {esc.what_happened}
                    </p>

                    <div className="pt-2">
                      <span className="text-xs font-semibold tracking-wider text-neutral-500 uppercase">
                        Agent Checks & Diagnostics
                      </span>
                      <p className="mt-0.5 text-xs text-neutral-400">{esc.checked_by_agent}</p>
                    </div>
                  </div>
                </div>

                {/* Footer Action Buttons */}
                <div className="flex flex-wrap items-center justify-end gap-2 border-t border-neutral-800/60 pt-2">
                  {esc.status !== 'in_progress' && (
                    <button
                      onClick={() => handleStatusChange(esc.escalation_id, 'in_progress')}
                      className="rounded-xl border border-purple-800/50 bg-purple-950/60 px-3.5 py-1.5 text-xs font-semibold text-purple-300 transition hover:bg-purple-900/60"
                    >
                      Mark In Progress
                    </button>
                  )}
                  {esc.status !== 'resolved' && (
                    <button
                      onClick={() => handleStatusChange(esc.escalation_id, 'resolved')}
                      className="rounded-xl border border-emerald-800/50 bg-emerald-950/60 px-3.5 py-1.5 text-xs font-semibold text-emerald-300 transition hover:bg-emerald-900/60"
                    >
                      Mark Resolved
                    </button>
                  )}
                  {esc.status === 'resolved' && (
                    <button
                      onClick={() => handleStatusChange(esc.escalation_id, 'open')}
                      className="rounded-xl border border-neutral-800 bg-neutral-900 px-3.5 py-1.5 text-xs font-semibold text-neutral-400 transition hover:bg-neutral-800"
                    >
                      Reopen Ticket
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
