"use client";

import { useEffect, useState, use } from "react";
import { useUser } from "@clerk/nextjs";
import Link from "next/link";

interface Artifact {
  id: string;
  license_key: string;
  realm_id: string | null;
  type: "report" | "analysis" | "reconciliation" | "export";
  name: string;
  description: string | null;
  data: TableData | ChartData | SummaryData | unknown;
  format: "table" | "chart" | "summary" | "pdf";
  tags: string[];
  starred: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

interface TableData {
  columns: string[];
  rows: (string | number)[][];
  totals?: (string | number)[];
}

interface ChartData {
  type: "bar" | "line" | "pie";
  labels: string[];
  datasets: { label: string; data: number[] }[];
}

interface SummaryData {
  title: string;
  sections: { heading: string; content: string }[];
  highlights?: { label: string; value: string }[];
}

export default function ReportDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { isLoaded, isSignedIn } = useUser();

  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      fetchArtifact();
    }
  }, [isLoaded, isSignedIn, id]);

  const fetchArtifact = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/artifacts/${id}`);
      if (res.ok) {
        const data = await res.json();
        setArtifact(data.artifact);
      } else {
        setError("Report not found");
      }
    } catch {
      setError("Failed to load report");
    } finally {
      setLoading(false);
    }
  };

  const toggleStar = async () => {
    if (!artifact) return;

    try {
      const res = await fetch(`/api/artifacts/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ starred: !artifact.starred }),
      });

      if (res.ok) {
        setArtifact({ ...artifact, starred: !artifact.starred });
      }
    } catch (err) {
      console.error("Failed to toggle star:", err);
    }
  };

  if (!isLoaded || loading) {
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
            Sign in to view this report
          </Link>
        </div>
      </div>
    );
  }

  if (error || !artifact) {
    return (
      <div className="min-h-screen bg-[#0a0f1c] flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white mb-4">
            {error || "Report not found"}
          </h1>
          <Link
            href="/dashboard/reports"
            className="text-cyan-400 hover:text-cyan-300"
          >
            Back to reports
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0f1c] py-8 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <Link
              href="/dashboard/reports"
              className="text-sm text-gray-400 hover:text-white mb-2 inline-block"
            >
              ← Back to Reports
            </Link>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl font-bold text-white">{artifact.name}</h1>
              <button
                onClick={toggleStar}
                className={`text-2xl transition ${
                  artifact.starred
                    ? "text-yellow-400"
                    : "text-gray-600 hover:text-yellow-400"
                }`}
              >
                ★
              </button>
            </div>
            {artifact.description && (
              <p className="text-gray-400">{artifact.description}</p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <TypeBadge type={artifact.type} />
            <FormatBadge format={artifact.format} />
          </div>
        </div>

        {/* Metadata */}
        <div className="flex flex-wrap gap-4 mb-6 text-sm text-gray-400">
          <span>
            Created{" "}
            {new Date(artifact.created_at).toLocaleDateString("en-US", {
              month: "long",
              day: "numeric",
              year: "numeric",
              hour: "numeric",
              minute: "2-digit",
            })}
          </span>
          <span>•</span>
          <span>Generated by {artifact.created_by}</span>
          {artifact.realm_id && (
            <>
              <span>•</span>
              <span>Company: {artifact.realm_id}</span>
            </>
          )}
        </div>

        {/* Tags */}
        {artifact.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-6">
            {artifact.tags.map((tag) => (
              <span
                key={tag}
                className="px-3 py-1 bg-white/5 rounded-full text-sm text-gray-400"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Content */}
        <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
          <RenderArtifactData artifact={artifact} />
        </div>
      </div>
    </div>
  );
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    report: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    analysis: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    reconciliation: "bg-green-500/10 text-green-400 border-green-500/20",
    export: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  };

  return (
    <span
      className={`px-3 py-1 rounded-lg border text-sm font-medium ${colors[type]}`}
    >
      {type}
    </span>
  );
}

function FormatBadge({ format }: { format: string }) {
  return (
    <span className="px-3 py-1 rounded-lg border border-white/10 bg-white/5 text-sm text-gray-400">
      {format}
    </span>
  );
}

function RenderArtifactData({ artifact }: { artifact: Artifact }) {
  const { format, data } = artifact;

  if (format === "table" && isTableData(data)) {
    return <TableRenderer data={data} />;
  }

  if (format === "summary" && isSummaryData(data)) {
    return <SummaryRenderer data={data} />;
  }

  // Fallback: render as JSON
  return (
    <div className="overflow-x-auto">
      <pre className="text-sm text-gray-300 whitespace-pre-wrap">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

function isTableData(data: unknown): data is TableData {
  return (
    typeof data === "object" &&
    data !== null &&
    "columns" in data &&
    "rows" in data &&
    Array.isArray((data as TableData).columns) &&
    Array.isArray((data as TableData).rows)
  );
}

function isSummaryData(data: unknown): data is SummaryData {
  return (
    typeof data === "object" &&
    data !== null &&
    "sections" in data &&
    Array.isArray((data as SummaryData).sections)
  );
}

function TableRenderer({ data }: { data: TableData }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-gray-400 border-b border-white/10">
            {data.columns.map((col, i) => (
              <th key={i} className="px-4 py-3 font-medium">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, i) => (
            <tr key={i} className="border-b border-white/5 hover:bg-white/5">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-3 text-white">
                  {typeof cell === "number" ? cell.toLocaleString() : cell}
                </td>
              ))}
            </tr>
          ))}
          {data.totals && (
            <tr className="border-t border-white/10 font-semibold">
              {data.totals.map((cell, i) => (
                <td key={i} className="px-4 py-3 text-cyan-400">
                  {typeof cell === "number" ? cell.toLocaleString() : cell}
                </td>
              ))}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function SummaryRenderer({ data }: { data: SummaryData }) {
  return (
    <div className="space-y-6">
      {data.title && (
        <h2 className="text-2xl font-bold text-white">{data.title}</h2>
      )}

      {data.highlights && data.highlights.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {data.highlights.map((h, i) => (
            <div key={i} className="bg-white/5 rounded-lg p-4">
              <p className="text-sm text-gray-400">{h.label}</p>
              <p className="text-2xl font-bold text-cyan-400">{h.value}</p>
            </div>
          ))}
        </div>
      )}

      {data.sections.map((section, i) => (
        <div key={i}>
          <h3 className="text-lg font-semibold text-white mb-2">
            {section.heading}
          </h3>
          <p className="text-gray-300 whitespace-pre-wrap">{section.content}</p>
        </div>
      ))}
    </div>
  );
}
