import { createContext, useContext, useState, ReactNode } from "react";
import client from "../api/client";

export type Role = "student" | "faculty" | "admin";

interface AuthUser {
  username: string;
  full_name: string;
  role: Role;
}

interface AuthContextValue {
  user: AuthUser | null;
  login: (username: string, password: string) => Promise<AuthUser>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function loadStoredUser(): AuthUser | null {
  const raw = localStorage.getItem("campusone_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(loadStoredUser());

  const login = async (username: string, password: string) => {
    const res = await client.post("/auth/login", { username, password });
    const { access_token, role, full_name, username: uname } = res.data;
    localStorage.setItem("campusone_token", access_token);
    const authUser: AuthUser = { username: uname, full_name, role };
    localStorage.setItem("campusone_user", JSON.stringify(authUser));
    setUser(authUser);
    return authUser;
  };

  const logout = () => {
    localStorage.removeItem("campusone_token");
    localStorage.removeItem("campusone_user");
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
