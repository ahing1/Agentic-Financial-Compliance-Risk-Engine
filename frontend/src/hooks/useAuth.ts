/**
 *
 * Manages login state across the app. Components use this hook
 * to check if the user is logged in, get their email, and
 * handle login/logout/register.
 */

"use client";

import { useState, useCallback } from "react";
import {
  login as apiLogin,
  register as apiRegister,
  logout as apiLogout,
  isAuthenticated,
  setToken,
} from "@/lib/api";
import type { TokenResponse } from "@/lib/types";

interface UseAuthReturn {
  isLoggedIn: boolean;
  userEmail: string | null;
  loginError: string | null;
  registerError: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
}

export function useAuth(): UseAuthReturn {
  const [isLoggedIn, setIsLoggedIn] = useState(isAuthenticated());
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [registerError, setRegisterError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const login = useCallback(async (email: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    setLoginError(null);

    try {
      const result = await apiLogin(email, password);
      setIsLoggedIn(true);
      setUserEmail(result.email);
      return true;
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "Login failed");
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (email: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    setRegisterError(null);

    try {
      await apiRegister(email, password);
      // Auto-login after registration
      return await login(email, password);
    } catch (err) {
      setRegisterError(err instanceof Error ? err.message : "Registration failed");
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [login]);

  const logout = useCallback(() => {
    apiLogout();
    setIsLoggedIn(false);
    setUserEmail(null);
  }, []);

  return {
    isLoggedIn,
    userEmail,
    loginError,
    registerError,
    isLoading,
    login,
    register,
    logout,
  };
}