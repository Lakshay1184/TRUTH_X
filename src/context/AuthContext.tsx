"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { useToast } from "@/context/ToastContext";

interface AuthContextType {
    user: any | null;
    login: (email: string, password?: string) => Promise<void>;
    signup: (email: string, password?: string, name?: string) => Promise<void>;
    logout: () => Promise<void>;
    isAuthenticated: boolean;
    loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<any | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const router = useRouter();
    const { showToast } = useToast();

    useEffect(() => {
        let mounted = true;

        async function restore() {
            try {
                setLoading(true);
                const {
                    data: { session },
                } = await supabase.auth.getSession();
                if (!mounted) return;
                setUser(session?.user ?? null);
            } catch (err: any) {
                console.error("Failed to restore session:", err);
            } finally {
                if (mounted) setLoading(false);
            }
        }

        restore();

        const { data } = supabase.auth.onAuthStateChange((_event, session) => {
            try {
                setUser(session?.user ?? null);
            } catch (e) {
                console.error("onAuthStateChange handler error:", e);
            }
        });

        const subscription = data?.subscription;

        return () => {
            mounted = false;
            if (subscription && typeof subscription.unsubscribe === "function") subscription.unsubscribe();
        };
    }, [showToast]);

    const login = async (email: string, password?: string) => {
        if (!password) {
            showToast("Password is required", "error");
            throw new Error("Password is required");
        }
        try {
            const { data, error } = await supabase.auth.signInWithPassword({ email, password });
            if (error) {
                showToast(error.message || "Sign in failed", "error");
                throw error;
            }
            // Update local user immediately
            const userObj = (data as any)?.user ?? (data as any)?.session?.user ?? null;
            setUser(userObj);
            showToast("Signed in successfully", "success");
            router.push("/");
        } catch (err: any) {
            console.error("Login error:", err);
            throw err;
        }
    };

    const signup = async (email: string, password?: string, name?: string) => {
        if (!password) {
            showToast("Password is required", "error");
            throw new Error("Password is required");
        }
        try {
            const { data, error } = await supabase.auth.signUp({
                email,
                password,
                options: {
                    data: {
                        full_name: name,
                    },
                },
            });
            if (error) {
                showToast(error.message || "Sign up failed", "error");
                throw error;
            }

            const userObj = (data as any)?.user ?? (data as any)?.session?.user ?? null;
            if (userObj) {
                setUser(userObj);
                showToast("Account created and signed in", "success");
                router.push("/");
                return;
            }

            // If no session returned, notify user to confirm email
            showToast("Account created. Please check your email to confirm your account.", "info");
            router.push("/");
        } catch (err: any) {
            console.error("Signup error:", err);
            throw err;
        }
    };

    const logout = async () => {
        try {
            const { error } = await supabase.auth.signOut();
            if (error) {
                showToast(error.message || "Sign out failed", "error");
                throw error;
            }
            setUser(null);
            showToast("Signed out", "info");
            router.push("/login");
        } catch (err) {
            console.error("Logout error:", err);
            throw err;
        }
    };

    return (
        <AuthContext.Provider value={{ user, login, signup, logout, isAuthenticated: !!user, loading }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
}
