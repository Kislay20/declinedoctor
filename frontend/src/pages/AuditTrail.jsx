import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Clock,
  ShieldAlert,
  Cpu,
  Play,
  CheckCircle,
  XCircle,
} from "lucide-react";
import api from "../api";

export default function AuditTrail() {
  const { id } = useParams();
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;

    // 1. Function ko useEffect ke andar define kiya
    const getAuditData = async () => {
      try {
        if (isMounted) setLoading(true);

        const [incidentRes, auditRes] = await Promise.all([
          api.get(`/incidents/${id}`),
          api.get(`/incidents/${id}/audit`),
        ]);

        if (!isMounted) return;

        const { incident } = incidentRes.data;
        const dbLogs = auditRes.data || [];
        const constructedTimeline = [];

        // Render real server-provided audit logs
        dbLogs.forEach((log) => {
          let parsedDetails;
          try {
            parsedDetails = typeof log.details_json === "string" ? JSON.parse(log.details_json) : (log.details_json || {});
          } catch {
            parsedDetails = { details: String(log.details_json) };
          }
          constructedTimeline.push({
            id: log.id,
            timestamp: log.timestamp,
            event_type: log.event_type,
            actor: log.actor || "system",
            details: parsedDetails,
          });
        });

        // Historical safety fallback only if older db record did not record ANOMALY_DETECTED
        const hasAnomalyDetected = constructedTimeline.some((e) => e.event_type === "ANOMALY_DETECTED");
        if (!hasAnomalyDetected && incident) {
          constructedTimeline.unshift({
            id: "fallback_detect",
            timestamp: incident.detected_at,
            event_type: "ANOMALY_DETECTED",
            actor: "system",
            details: {
              segment: `${incident.segment_issuer} ${incident.segment_payment_method}`,
              drop_pp: `${incident.drop_pp?.toFixed(1)}%`,
              sample_size: incident.sample_size,
            },
          });
        }

        // Sort chronologically
        constructedTimeline.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        if (isMounted) {
          setTimeline(constructedTimeline);
          setError(null);
        }
      } catch (err) {
        console.error(err);
        if (isMounted) setError("Failed to load audit trail.");
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    // 3. Yahan usko call kiya
    getAuditData();

    // 4. Cleanup function
    return () => {
      isMounted = false;
    };
  }, [id]);

  const getEventIcon = (type) => {
    switch (type) {
      case "ANOMALY_DETECTED":
        return <ShieldAlert className="w-5 h-5 text-rose-500" />;
      case "DIAGNOSED":
        return <Cpu className="w-5 h-5 text-purple-400" />;
      case "ACTION_SELECTED":
        return <Play className="w-5 h-5 text-blue-400" />;
      case "OUTCOME_MEASURED":
        return <CheckCircle className="w-5 h-5 text-emerald-400" />;
      case "ESCALATION":
        return <XCircle className="w-5 h-5 text-orange-400" />;
      case "HUMAN_APPROVAL_REQUIRED":
        return <ShieldAlert className="w-5 h-5 text-amber-400" />;
      default:
        return <Clock className="w-5 h-5 text-slate-400" />;
    }
  };

  const getEventColor = (type) => {
    switch (type) {
      case "ANOMALY_DETECTED":
        return "border-rose-500/30 bg-rose-500/10";
      case "DIAGNOSED":
        return "border-purple-500/30 bg-purple-500/10";
      case "ACTION_SELECTED":
        return "border-blue-500/30 bg-blue-500/10";
      case "OUTCOME_MEASURED":
        return "border-emerald-500/30 bg-emerald-500/10";
      case "ESCALATION":
        return "border-orange-500/30 bg-orange-500/10";
      case "HUMAN_APPROVAL_REQUIRED":
        return "border-amber-500/30 bg-amber-500/10";
      default:
        return "border-slate-700 bg-slate-800";
    }
  };

  if (loading)
    return (
      <div className="text-center py-10 text-slate-400">
        Loading audit trail...
      </div>
    );
  if (error)
    return <div className="text-center py-10 text-rose-400">{error}</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4 bg-[#1e2330] p-6 rounded-xl border border-slate-800">
        <Link
          to={`/incident/${id}`}
          className="p-2 hover:bg-slate-800 rounded-lg transition text-slate-400 hover:text-white"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-white">System Audit Trail</h1>
          <p className="text-slate-400 text-sm mt-1">
            Chronological record of detection, diagnosis, and actions.
          </p>
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-[#1e2330] p-8 rounded-xl border border-slate-800">
        {timeline.length === 0 ? (
          <div className="text-center text-slate-500 py-6">
            No events recorded yet.
          </div>
        ) : (
          <div className="relative border-l-2 border-slate-700 ml-4 space-y-8">
            {timeline.map((event, index) => (
              <div key={event.id || index} className="relative pl-8">
                {/* Timeline Node */}
                <div className="absolute -left-[13px] top-1 bg-[#1e2330] p-1 rounded-full border border-slate-700">
                  {getEventIcon(event.event_type)}
                </div>

                {/* Event Card */}
                <div
                  className={`p-4 rounded-lg border ${getEventColor(event.event_type)}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="font-bold text-slate-200">
                      {event.event_type.replace(/_/g, " ")}
                    </h3>
                    <span className="text-xs text-slate-500 font-mono">
                      {new Date(event.timestamp).toLocaleString()}
                    </span>
                  </div>

                  <div className="text-sm text-slate-300 space-y-1">
                    <div className="text-xs text-slate-500 mb-2">
                      Actor:{" "}
                      <span className="font-semibold text-slate-400">
                        {event.actor.toUpperCase()}
                      </span>
                    </div>

                    {/* Render JSON Details dynamically */}
                    {Object.entries(event.details).map(([key, value]) => (
                      <div key={key} className="flex gap-2">
                        <span className="text-slate-400 capitalize w-32">
                          {key.replace(/_/g, " ")}:
                        </span>
                        <span className="font-medium text-white">
                          {String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
