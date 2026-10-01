import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const DEMO_ACCOUNTS = [
  { role: "Admin", username: "admin", password: "admin123" },
  { role: "Faculty", username: "faculty1", password: "faculty123" },
  { role: "Student", username: "student1", password: "student123" },
];

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await login(username, password);
      navigate(`/${user.role}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Login failed. Check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-paper">
      <div className="hidden lg:flex flex-col justify-between bg-navy text-paper p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-[0.06]" style={{
          backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
          backgroundSize: "24px 24px",
        }} />
        <div className="relative">
          <p className="font-display text-2xl">CampusOne <span className="text-brassLight">AI</span></p>
        </div>
        <div className="relative max-w-md">
          <p className="font-display text-4xl leading-tight">
            One portal for every record, result, and requirement on campus.
          </p>
          <p className="text-paper/60 mt-4 text-sm leading-relaxed">
            Attendance, marks, timetables, fees, placements, and an AI assistant that
            actually knows your data — all in one place.
          </p>
        </div>
        <div className="relative text-xs text-paper/40">
          Academic Year 2026–27 · Odd Semester
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="lg:hidden mb-8">
            <p className="font-display text-2xl text-ink">CampusOne <span className="text-brass">AI</span></p>
          </div>
          <h1 className="font-display text-2xl text-ink">Sign in to your portal</h1>
          <p className="text-sm text-slate mt-1.5">Use your university credentials to continue.</p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <label className="text-sm text-ink font-medium block mb-1.5">Username</label>
              <input
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. student1"
                autoFocus
              />
            </div>
            <div>
              <label className="text-sm text-ink font-medium block mb-1.5">Password</label>
              <input
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            {error && <p className="text-sm text-clay">{error}</p>}
            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-black/5">
            <p className="text-xs text-slate mb-2.5">Demo accounts (for evaluation)</p>
            <div className="grid grid-cols-3 gap-2">
              {DEMO_ACCOUNTS.map((a) => (
                <button
                  key={a.username}
                  onClick={() => fillDemo(a.username, a.password)}
                  className="btn-secondary text-xs py-2 px-2"
                  type="button"
                >
                  {a.role}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
