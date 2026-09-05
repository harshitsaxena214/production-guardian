"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { 
  Activity, 
  AlertTriangle, 
  Film, 
  Search, 
  ShieldAlert, 
  Terminal,
  Settings
} from "lucide-react"

import { cn } from "@/lib/utils"

const navigation = [
  { name: "Overview", href: "/", icon: Film },
  { name: "Incidents", href: "/incidents", icon: AlertTriangle },
  { name: "Telemetry", href: "/telemetry", icon: Activity },
  { name: "Agent Hub", href: "/agent", icon: Terminal },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <div className="flex h-full w-64 flex-col border-r bg-card">
      <div className="flex h-16 shrink-0 items-center border-b px-6">
        <ShieldAlert className="mr-2 h-6 w-6 text-red-500" />
        <span className="text-lg font-bold tracking-tight">Production Guardian</span>
      </div>

      <div className="flex flex-1 flex-col overflow-y-auto px-4 py-4">
        <nav className="flex-1 space-y-1">
          {navigation.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href))
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  isActive
                    ? "bg-secondary text-primary font-medium"
                    : "text-muted-foreground hover:bg-secondary/50 hover:text-primary",
                  "group flex items-center rounded-md px-3 py-2 text-sm transition-colors"
                )}
              >
                <item.icon
                  className={cn(
                    isActive ? "text-primary" : "text-muted-foreground group-hover:text-primary",
                    "mr-3 h-5 w-5 flex-shrink-0 transition-colors"
                  )}
                  aria-hidden="true"
                />
                {item.name}
              </Link>
            )
          })}
        </nav>
        
        <div className="mt-8 border-t pt-4">
          <div className="rounded-lg border bg-background p-4 text-xs">
            <div className="mb-2 flex items-center text-muted-foreground">
              <div className="mr-2 h-2 w-2 rounded-full bg-red-500 animate-pulse" />
              DEMO MODE
            </div>
            <p className="text-muted-foreground">
              Connected to local simulator and Grafana Cloud MCP.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
