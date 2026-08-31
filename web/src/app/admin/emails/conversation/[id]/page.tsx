import { getSupabase } from "@/lib/supabase";
import { redirect } from "next/navigation";
import { currentUser } from "@clerk/nextjs/server";
import Link from "next/link";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

interface Conversation {
  id: string;
  license_key: string | null;
  user_email: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

async function getConversation(
  id: string,
): Promise<{ conversation: Conversation; messages: Message[] } | null> {
  const supabase = getSupabase();

  const { data: conversation } = await supabase
    .from("support_conversations")
    .select("*")
    .eq("id", id)
    .single();

  if (!conversation) return null;

  // support_conversations has no user_email column — derive identity from the
  // linked license, then the conversation metadata, then the anonymous id.
  const conv = conversation as Record<string, unknown>;
  let userEmail: string | null = null;
  const licenseKey = conv.license_key as string | null;
  if (licenseKey) {
    const { data: lic } = await supabase
      .from("licenses")
      .select("email")
      .eq("key", licenseKey)
      .single();
    userEmail = lic?.email ?? null;
  }
  if (!userEmail) {
    const meta = (conv.metadata || {}) as { email?: string };
    userEmail =
      meta.email ??
      (conv.anonymous_id
        ? `anon:${String(conv.anonymous_id).slice(0, 8)}`
        : null);
  }

  const { data: messages } = await supabase
    .from("support_messages")
    .select("id, role, content, created_at")
    .eq("conversation_id", id)
    .order("created_at", { ascending: true });

  return {
    conversation: { ...(conversation as Conversation), user_email: userEmail },
    messages: (messages || []) as Message[],
  };
}

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await currentUser();
  if (!user) {
    redirect("/sign-in");
  }

  const role = (user.publicMetadata as { role?: string })?.role;
  if (role !== "admin") {
    redirect("/dashboard");
  }

  const { id } = await params;
  const data = await getConversation(id);

  if (!data) {
    return (
      <div className="text-center py-12">
        <h1 className="text-2xl font-bold text-white">
          Conversation Not Found
        </h1>
        <p className="text-gray-400 mt-2">
          This conversation doesn&apos;t exist.
        </p>
        <Link
          href="/admin/emails"
          className="text-cyan-400 hover:text-cyan-300 mt-4 inline-block"
        >
          ← Back to Emails
        </Link>
      </div>
    );
  }

  const { conversation, messages } = data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link
            href="/admin/emails"
            className="text-sm text-cyan-400 hover:text-cyan-300"
          >
            ← Back to Emails
          </Link>
          <h1 className="text-2xl font-bold text-white mt-2">
            Support Conversation
          </h1>
        </div>
        <StatusBadge status={conversation.status} />
      </div>

      {/* Conversation Info */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-gray-400">User Email</p>
            <p className="text-white mt-1">
              {conversation.user_email || "Anonymous"}
            </p>
          </div>
          <div>
            <p className="text-gray-400">License Key</p>
            <p className="text-white mt-1 font-mono text-xs">
              {conversation.license_key || "Not provided"}
            </p>
          </div>
          <div>
            <p className="text-gray-400">Created</p>
            <p className="text-white mt-1">
              {formatDateTime(conversation.created_at)}
            </p>
          </div>
          <div>
            <p className="text-gray-400">Last Update</p>
            <p className="text-white mt-1">
              {formatDateTime(conversation.updated_at)}
            </p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Transcript</h2>
        <div className="space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`p-4 rounded-lg ${
                message.role === "user"
                  ? "bg-blue-500/10 border border-blue-500/20"
                  : "bg-white/5 border border-white/10"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span
                  className={`text-sm font-medium ${
                    message.role === "user" ? "text-blue-400" : "text-gray-400"
                  }`}
                >
                  {message.role === "user" ? "Customer" : "AI Agent"}
                </span>
                <span className="text-xs text-gray-500">
                  {formatDateTime(message.created_at)}
                </span>
              </div>
              <p className="text-white whitespace-pre-wrap">
                {message.content}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    escalated: "bg-red-500/10 text-red-400 border-red-500/20",
    resolved: "bg-green-500/10 text-green-400 border-green-500/20",
    open: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  };

  return (
    <span
      className={`px-3 py-1 rounded-full text-sm font-medium border ${colors[status] || "bg-gray-500/10 text-gray-400 border-gray-500/20"}`}
    >
      {status}
    </span>
  );
}

function formatDateTime(date: string): string {
  return new Date(date).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
