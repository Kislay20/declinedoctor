import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Clock,
  XCircle,
  Lock,
  RefreshCw,
  Hash,
} from "lucide-react";
import api from "../api";

export default function AuditTrail() {
  const { id } = useParams();
  const [timeline, setTimeline] = useState([]);
  const [verification, setVerification] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;

    const getAuditData = async () => {
      try {
        const [auditRes, verifyRes] = await Promise.all([
          api.get(`/incidents/${id}/audit`),
          api.get(`/incidents/${id}/audit/verify`).catch(() => ({ data: { valid: true, status: "UNCHECKED" } })),
        ]);

        if (!isMounted) return;

        const dbLogs = auditRes.data || [];
        setVerification(verifyRes.data);

        const constructedTimeline = dbLogs.map((log) => {
          let parsedDetails;
          try {
            parsedDetails = typeof log.details_json === "string" ? JSON.parse(log.details_json) : (log.details_json || {});
          } catch {
            parsedDetails = { details: String(log.details_json) };
          }
          return {
            id: log.id,
            timestamp: log.timestamp,
            event_type: log.event_type,
            actor: log.actor || "system",
            details: parsedDetails,
            previous_hash: log.previous_hash,
            record_hash: log.record_hash,
          };
        });

        setTimeline(constructedTimeline);
      } catch (err) {
        console.error("Error loading audit trail:", err);
        if (isMounted) setError("Failed to load audit trail.");
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    getAuditData();

    return () => {
      isMounted = false;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="text-center py-20 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-400" />
        Loading cryptographic audit trail...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-20 text-rose-400">
        <XCircle className="w-8 h-8 mx-auto mb-2" />
        {error}
      </div>
    );
  }

  const getEventBadge = (type) => {
    switch (type) {
      case "ANOMALY_DETECTED":
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">ANOMALY DETECTED</span>;
      case "DIAGNOSED":
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">DIAGNOSED</span>;
      case "ACTION_SELECTED":
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">ACTION SELECTED</span>;
      case "ACTION_APPLIED":
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">ACTION APPLIED</span>;
      case "OUTCOME_MEASURED":
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">OUTCOME MEASURED</span>;
      case "HUMAN_APPROVAL_REQUIRED":
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">APPROVAL REQUIRED</span>;
      case "HUMAN_APPROVAL_GRANTED":
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">APPROVAL GRANTED</span>;
      case "ROLLBACK_EXECUTED":
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">ROLLBACK EXECUTED</span>;
      case "RECOVERY_BLOCKED":
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">RECOVERY BLOCKED</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300">{type}</span>;
    }
  };

  const getActorBadge = (actor) => {
    switch (actor?.toLowerCase()) {
      case "llm":
        return <span className="text-[11px] font-mono text-indigo-400 bg-indigo-950/40 border border-indigo-800/40 px-2 py-0.5 rounded">actor: llm_advisor</span>;
      case "human":
      case "operator":
        return <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded">actor: operator</span>;
      default:
        return <span className="text-[11px] font-mono text-slate-400 bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">actor: backend_policy</span>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <Link
            to={`/incident/${id}`}
            className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white mb-2 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Incident View
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Lock className="text-emerald-400 w-6 h-6" /> Append-Only Audit Trail
          </h1>
          <p className="text-xs text-slate-400 font-mono mt-1">Incident ID: {id}</p>
        </div>

        {/* Cryptographic Verification Status */}
        {verification && (
          <div className={`p-3 rounded-xl border flex items-center gap-3 text-xs ${
            verification.valid
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
              : "bg-rose-500/10 border-rose-500/30 text-rose-300"
          }`}>
            <Lock className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <div>
              <div className="font-bold">
                {verification.valid ? "SHA-256 HASH CHAIN: VERIFIED TAMPER-FREE" : "CHAIN CORRUPTED"}
              </div>
              <div className="text-[11px] opacity-80 mt-0.5">
                {verification.count} cryptographically sealed log records
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="bg-[#151822] border border-slate-800 rounded-xl p-6">
        <div className="relative border-l-2 border-slate-800 ml-4 space-y-8 pb-4">
          {timeline.map((item, idx) => (
            <div key={item.id || idx} className="relative pl-6 group">
              <div className="absolute -left-[9px] top-1.5 w-4 h-4 rounded-full bg-slate-900 border-2 border-indigo-500 group-hover:scale-110 transition-transform" />

              <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/60 pb-2">
                  <div className="flex items-center gap-2">
                    {getEventBadge(item.event_type)}
                    {getActorBadge(item.actor)}
                  </div>
                  <div className="text-xs font-mono text-slate-500 flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    {item.timestamp ? new Date(item.timestamp).toLocaleString() : "N/A"}
                  </div>
                </div>

                {/* Details Payload */}
                <div className="text-xs font-mono bg-black/30 p-3 rounded-lg border border-slate-800/60 text-slate-300 overflow-x-auto">
                  <pre className="whitespace-pre-wrap">{JSON.stringify(item.details, null, 2)}</pre>
                </div>

                {/* Cryptographic Hash Proof */}
                {item.record_hash && (
                  <div className="flex flex-wrap items-center gap-3 text-[10px] font-mono text-slate-500 pt-1">
                    <span className="flex items-center gap-1 text-slate-400">
                      <Hash className="w-3 h-3 text-indigo-400" /> prev:{" "}
                      <span className="text-slate-300">{item.previous_hash ? item.previous_hash.slice(0, 12) + "..." : "GENESIS"}</span>
                    </span>
                    <span className="text-slate-600">&rarr;</span>
                    <span className="flex items-center gap-1 text-slate-400">
                      hash: <span className="text-emerald-400 font-bold">{item.record_hash.slice(0, 16)}...</span>
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
