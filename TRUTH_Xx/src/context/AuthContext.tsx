"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useRouter } from "next/navigation";

interface AuthContextType {
    user: { email: string } | null;
    login: (email: string) => void;
    signup: (email: string) => void;
    logout: () => void;
    isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<{ email: string } | null>(null);
    const router = useRouter();

    useEffect(() => {
        // Check local storage on mount
        const storedUser = localStorage.getItem("truth_x_user");
        if (storedUser) {
            setUser(JSON.parse(storedUser));
        }
    }, []);

    const login = (email: string) => {
        const newUser = { email };
        setUser(newUser);
        localStorage.setItem("truth_x_user", JSON.stringify(newUser));
        router.push("/");
    };

    const signup = (email: string) => {
        const newUser = { email };
        setUser(newUser);
        localStorage.setItem("truth_x_user", JSON.stringify(newUser));
        router.push("/");
    };

    const logout = () => {
        setUser(null);
        localStorage.removeItem("truth_x_user");
        router.push("/login");
    };

    return (
        <AuthContext.Provider value={{ user, login, signup, logout, isAuthenticated: !!user }}>
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
