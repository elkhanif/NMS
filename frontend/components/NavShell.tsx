"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "@/lib/auth-context";

interface NavItem {
  href: string;
  label: string;
  adminOnly?: boolean;
  configWriterOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard" },
  { href: "/whats-happening", label: "What's Happening" },
  { href: "/devices", label: "Devices" },
  { href: "/network-map", label: "Network Map" },
  { href: "/detective", label: "Detective" },
  { href: "/incidents", label: "Incidents" },
  { href: "/alerts", label: "Alerts" },
  { href: "/events", label: "Events" },
  { href: "/discovery", label: "Discovery" },
  { href: "/settings/alert-rules", label: "Alert Rules", configWriterOnly: true },
  { href: "/settings/users", label: "Users", adminOnly: true },
];

export function NavShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { email, role, isAdmin, isConfigWriter, logout, loading } = useAuth();

  if (pathname === "/login") return <>{children}</>;

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-panelborder bg-panel/60 p-4 flex flex-col gap-1">
        <div className="mb-4 px-2">
          <div className="text-lg font-bold text-gray-100">Mini NMS</div>
          <div className="text-xs text-gray-500">Network Monitoring</div>
        </div>
        {NAV_ITEMS.filter((item) => {
          if (item.adminOnly && !isAdmin) return false;
          if (item.configWriterOnly && !isConfigWriter) return false;
          return true;
        }).map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={clsx(
              "rounded-md px-3 py-2 text-sm",
              pathname === item.href ? "bg-blue-600 text-white" : "text-gray-300 hover:bg-white/5"
            )}
          >
            {item.label}
          </Link>
        ))}
        <div className="mt-auto px-2 pt-4 border-t border-panelborder text-xs text-gray-500">
          {!loading && (
            <>
              <div className="truncate">{email}</div>
              <div className="text-gray-600">{role}</div>
              <button onClick={logout} className="mt-2 text-blue-400 hover:underline">
                Log out
              </button>
            </>
          )}
        </div>
      </aside>
      <main className="flex-1 p-6 overflow-x-hidden">{children}</main>
    </div>
  );
}
