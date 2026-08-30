"use client";

import { useEffect, useState } from "react";
import { useUser } from "@clerk/nextjs";
import Link from "next/link";

interface Artifact {
  id: string;
  license_key: string;
  realm_id: string | null;
  type: "report" | "analysis" | "reconciliation" | "export";
  name: string;
  description: string | null;
  data: Record<string, unknown>;
  format: "table" | "chart" | "summary" | "pdf";
  tags: string[];
  starred: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

interface License {
  key: string;
  tier: string;
}

export default function ReportsPage() {
  const { isLoaded, isSignedIn } = useUser();

  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [licenses, setLicenses] = useState<License[]>([]);
  const [selectedLicense, setSelectedLicense] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [starredOnly, setStarredOnly] = useState(false);

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      fetchLicenses();
    }
  }, [isLoaded, isSignedIn]);

  useEffect(() => {
    if (selectedLicense) {
      fetchArtifacts();
    }
  }, [selectedLicense, filter, starredOnly]);

  const fetchLicenses = async () => {
    try {
      const res = await fetch("/api/user/licenses");
      if (res.ok) {
        const data = await res.json();
        setLicenses(data.licenses || []);
        if (data.licenses?.length > 0) {
          setSelectedLicense(data.licenses[0].key);
        }
      }
    } catch (err) {
      console.error("Failed to fetch licenses:", err);
    }
  };

  const fetchArtifacts = async () => {
    if (!selectedLicense) return;

    setLoading(true);
    try {
      const params = new URLSearchParams({ licenseKey: selectedLicense });
      if (filter !== "all") params.set("type", filter);
      if (starredOnly) params.set("starred", "true");

      const res = await fetch(`/api/artifacts?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setArtifacts(data.artifacts || []);
      }
    } catch (err) {
      console.error("Failed to fetch artifacts:", err);
    } finally {
      setLoading(false);
    }
  };

  const toggleStar = async (id: string, currentStarred: boolean) => {
    try {
      const res = await fetch(`/api/artifacts/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ starred: !currentStarred }),
      });

      if (res.ok) {
        setArtifacts((prev) =>
          prev.map((a) =>
            a.id === id ? { ...a, starred: !currentStarred } : a,
          ),
        );
      }
    } catch (err) {
      console.error("Failed to toggle star:", err);
    }
  };

  const deleteArtifact = async (id: string) => {
    if (!confirm("Are you sure you want to delete this report?")) return;

    try {
      const res = await fetch(`/api/artifacts/${id}`, { method: "DELETE" });
      if (res.ok) {
        setArtifacts((prev) => prev.filter((a) => a.id !== id));
      }
    } catch (err) {
      console.error("Failed to delete artifact:", err);
    }
  };

  if (!isLoaded) {
    return (
      <div className="min-h-screen bg-[#0a0f1c] flex items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!isSignedIn) {
    return (
      <div className="min-h-screen bg-[#0a0f1c] flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white mb-4">
            Sign in required
          </h1>
          <Link href="/sign-in" className="text-cyan-400 hover:text-cyan-300">
            Sign in to view your reports
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0f1c] py-8 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <Link
              href="/dashboard"
              className="text-sm text-gray-400 hover:text-white mb-2 inline-block"
            >
              ← Back to Dashboard
            </Link>
            <h1 className="text-3xl font-bold text-white">Reports & Exports</h1>
            <p className="text-gray-400 mt-1">
              View and manage Claude-generated reports
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          {licenses.length > 1 && (
            <select
              value={selectedLicense || ""}
              onChange={(e) => setSelectedLicense(e.target.value)}
              className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white focus:border-cyan-500/50 focus:outline-none"
            >
              {licenses.map((l) => (
                <option key={l.key} value={l.key}>
                  {l.key.substring(0, 12)}... ({l.tier})
                </option>
              ))}
            </select>
          )}

          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white focus:border-cyan-500/50 focus:outline-none"
          >
            <option value="all">All Types</option>
            <option value="report">Reports</option>
            <option value="analysis">Analyses</option>
            <option value="reconciliation">Reconciliations</option>
            <option value="export">Exports</option>
          </select>

          <button
            onClick={() => setStarredOnly(!starredOnly)}
            className={`px-4 py-2 rounded-lg border transition ${
              starredOnly
                ? "border-yellow-500/50 bg-yellow-500/10 text-yellow-400"
                : "border-white/10 bg-white/5 text-gray-400 hover:text-white"
            }`}
          >
            ★ Starred Only
          </button>
        </div>

        {/* Artifacts Grid */}
        {loading ? (
          <div className="text-center py-20">
            <div className="text-gray-400">Loading reports...</div>
          </div>
        ) : artifacts.length === 0 ? (
          <div className="text-center py-20">
            <div className="text-6xl mb-4">📊</div>
            <h2 className="text-xl text-white mb-2">No reports yet</h2>
            <p className="text-gray-400 max-w-md mx-auto">
              When Claude generates reports, analyses, or exports from your
              QuickBooks data, they&apos;ll appear here for easy access.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {artifacts.map((artifact) => (
              <ArtifactCard
                key={artifact.id}
                artifact={artifact}
                onToggleStar={() => toggleStar(artifact.id, artifact.starred)}
                onDelete={() => deleteArtifact(artifact.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ArtifactCard({
  artifact,
  onToggleStar,
  onDelete,
}: {
  artifact: Artifact;
  onToggleStar: () => void;
  onDelete: () => void;
}) {
  const typeIcons: Record<string, string> = {
    report: "📊",
    analysis: "🔍",
    reconciliation: "⚖️",
    export: "📁",
  };

  const typeColors: Record<string, string> = {
    report: "bg-blue-500/10 text-blue-400",
    analysis: "bg-purple-500/10 text-purple-400",
    reconciliation: "bg-green-500/10 text-green-400",
    export: "bg-orange-500/10 text-orange-400",
  };

  return (
    <div className="bg-[#131a2e] rounded-xl border border-white/10 p-5 hover:border-white/20 transition">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{typeIcons[artifact.type]}</span>
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium ${typeColors[artifact.type]}`}
          >
            {artifact.type}
          </span>
        </div>
        <button
          onClick={onToggleStar}
          className={`text-xl transition ${
            artifact.starred
              ? "text-yellow-400"
              : "text-gray-600 hover:text-yellow-400"
          }`}
        >
          ★
        </button>
      </div>

      <h3 className="text-lg font-semibold text-white mb-1 line-clamp-2">
        {artifact.name}
      </h3>

      {artifact.description && (
        <p className="text-sm text-gray-400 mb-3 line-clamp-2">
          {artifact.description}
        </p>
      )}

      {artifact.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {artifact.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 bg-white/5 rounded text-xs text-gray-400"
            >
              {tag}
            </span>
          ))}
          {artifact.tags.length > 3 && (
            <span className="px-2 py-0.5 text-xs text-gray-500">
              +{artifact.tags.length - 3}
            </span>
          )}
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-white/5">
        <span className="text-xs text-gray-500">
          {new Date(artifact.created_at).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </span>

        <div className="flex gap-2">
          <Link
            href={`/dashboard/reports/${artifact.id}`}
            className="px-3 py-1 text-sm bg-cyan-500/10 text-cyan-400 rounded hover:bg-cyan-500/20 transition"
          >
            View
          </Link>
          <button
            onClick={onDelete}
            className="px-3 py-1 text-sm bg-red-500/10 text-red-400 rounded hover:bg-red-500/20 transition"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
