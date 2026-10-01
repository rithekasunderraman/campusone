import { useEffect, useRef, useState } from "react";
import { Bot, Send, User as UserIcon } from "lucide-react";
import client from "../api/client";
import { useAuth } from "../context/AuthContext";
import { PageHeader } from "../components/Common";

interface Message {
  role: "user" | "assistant";
  text: string;
}

const SUGGESTIONS: Record<string, string[]> = {
  student: ["What is my attendance?", "What are my marks?", "What is my CGPA?", "Show my timetable",
             "When is my next exam?", "Which companies am I eligible for?", "What is my fees status?"],
  faculty: ["What subjects do I teach?", "Show attendance for my classes", "Show class performance",
             "What is my exam schedule?", "Show my timetable"],
  admin: ["How many students are enrolled?", "Show department overview", "What is the placement summary?",
           "What is the overall attendance?"],
};

export default function AIAssistant() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: `Hi ${user?.full_name.split(" ")[0] || ""}! I'm your CampusOne AI assistant. Ask me about your ${user?.role === "student" ? "attendance, marks, timetable, fees, or placements" : user?.role === "faculty" ? "subjects, classes, attendance, or exam schedule" : "institution-wide statistics and reports"}.` },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || sending) return;
    setMessages((m) => [...m, { role: "user", text: msg }]);
    setInput("");
    setSending(true);
    try {
      const res = await client.post("/ai/chat", { message: msg });
      setMessages((m) => [...m, { role: "assistant", text: res.data.response }]);
    } catch (err: any) {
      setMessages((m) => [...m, { role: "assistant", text: "Sorry, I couldn't process that just now. Please try again." }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <PageHeader title="AI Campus Assistant" subtitle="Ask questions about your own records — answers are pulled directly from the database." />

      <div className="flex-1 card p-5 flex flex-col min-h-0">
        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
              <div className={`h-8 w-8 rounded-full flex items-center justify-center shrink-0 ${m.role === "user" ? "bg-navy text-paper" : "bg-brass/15 text-brass"}`}>
                {m.role === "user" ? <UserIcon size={15} /> : <Bot size={15} />}
              </div>
              <div className={`max-w-[75%] rounded-xl px-4 py-2.5 text-sm whitespace-pre-line ${m.role === "user" ? "bg-navy text-paper" : "bg-black/[0.04] text-ink"}`}>
                {m.text}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex gap-3">
              <div className="h-8 w-8 rounded-full flex items-center justify-center bg-brass/15 text-brass"><Bot size={15} /></div>
              <div className="rounded-xl px-4 py-2.5 text-sm bg-black/[0.04] text-slate">Thinking…</div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="pt-4 mt-4 border-t border-black/5">
          <div className="flex gap-2 flex-wrap mb-3">
            {(SUGGESTIONS[user?.role || "student"] || []).map((s) => (
              <button key={s} onClick={() => send(s)} className="text-xs px-3 py-1.5 rounded-full border border-black/10 text-slate hover:bg-black/[0.03]">
                {s}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              className="input flex-1"
              placeholder="Type your question…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
            />
            <button className="btn-primary px-4" onClick={() => send()} disabled={sending}>
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
