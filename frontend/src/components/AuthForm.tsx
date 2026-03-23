"use client";

import { useState } from "react";

interface AuthFormProps {
  onLogin: (email: string, password: string) => Promise<boolean>;
  onRegister: (email: string, password: string) => Promise<boolean>;
  loginError: string | null;
  registerError: string | null;
  isLoading: boolean;
}

export default function AuthForm({
  onLogin,
  onRegister,
  loginError,
  registerError,
  isLoading,
}: AuthFormProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const EMAIL_REGEX = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;

  function validateForm(): string | null {
    if (mode !== "register") return null;

    const trimmedEmail = email.trim().toLowerCase();
    if (!EMAIL_REGEX.test(trimmedEmail) || trimmedEmail.includes("..")) {
      return "Please enter a valid email address";
    }
    if (password.length < 8) {
      return "Password must be at least 8 characters";
    }
    if (/^\d+$/.test(password)) {
      return "Password cannot be all numbers";
    }
    if (/^[a-zA-Z]+$/.test(password)) {
      return "Password must contain at least one number or special character";
    }
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) return;

    const error = validateForm();
    if (error) {
      setValidationError(error);
      return;
    }
    setValidationError(null);

    if (mode === "login") {
      await onLogin(email, password);
    } else {
      await onRegister(email, password);
    }
  };

  const error = validationError || (mode === "login" ? loginError : registerError);

  return (
    <div className="max-w-sm mx-auto mt-20">
      <h2 className="text-2xl font-semibold text-gray-900 text-center mb-2">
        Compliance Engine
      </h2>
      <p className="text-sm text-gray-500 text-center mb-8">
        {mode === "login" ? "Sign in to your account" : "Create a new account"}
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="email"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-md
                       focus:outline-none focus:ring-2 focus:ring-blue-500
                       disabled:bg-gray-100"
          />
        </div>

        <div>
          <label
            htmlFor="password"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={mode === "register" ? "Min 8 characters" : ""}
            required
            minLength={mode === "register" ? 8 : undefined}
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-md
                       focus:outline-none focus:ring-2 focus:ring-blue-500
                       disabled:bg-gray-100"
          />
        </div>

        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}

        <button
          type="submit"
          disabled={isLoading || !email.trim() || !password}
          className="w-full py-2 bg-blue-600 text-white rounded-md font-medium
                     hover:bg-blue-700 disabled:bg-gray-400
                     disabled:cursor-not-allowed transition-colors"
        >
          {isLoading
            ? "Please wait..."
            : mode === "login"
            ? "Sign In"
            : "Create Account"
          }
        </button>
      </form>

      <p className="text-sm text-gray-500 text-center mt-4">
        {mode === "login" ? (
          <>
            Don&apos;t have an account?{" "}
            <button
              onClick={() => setMode("register")}
              className="text-blue-600 hover:text-blue-800"
            >
              Sign up
            </button>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <button
              onClick={() => setMode("login")}
              className="text-blue-600 hover:text-blue-800"
            >
              Sign in
            </button>
          </>
        )}
      </p>
    </div>
  );
}