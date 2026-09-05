"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Terminal, Database, Network, Wrench } from "lucide-react"

export default function AgentPage() {
  const agents = [
    {
      name: "Orchestrator Agent",
      role: "Coordinator",
      model: "gemini-1.5-pro",
      description: "Manages the overall incident investigation lifecycle, delegates tasks to specialist agents, and coordinates SSE streaming to the frontend.",
      icon: Terminal,
      tools: ["delegate_investigation", "delegate_impact_analysis", "delegate_remediation"]
    },
    {
      name: "Investigation Agent",
      role: "Diagnostic Specialist",
      model: "gemini-1.5-pro",
      description: "Specializes in infrastructure diagnostics. Interfaces directly with Grafana via MCP to query metrics, logs, and alerts.",
      icon: Network,
      tools: ["query_prometheus", "query_loki", "get_alerts", "compare_baseline"]
    },
    {
      name: "Production Impact Agent",
      role: "Business Logic",
      model: "gemini-1.5-pro",
      description: "Correlates technical telemetry with production context (scenes, deadlines, footage) using deterministic calculations.",
      icon: Database,
      tools: ["get_production_context", "get_scene_context", "calculate_ingest_delay"]
    },
    {
      name: "Remediation Agent",
      role: "Operations",
      model: "gemini-1.5-flash",
      description: "Generates safe, structured remediation recommendations based on the verified root cause and production context.",
      icon: Wrench,
      tools: ["generate_remediation_plan", "verify_recovery_metrics"]
    }
  ]

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Agent Hub</h1>
          <p className="text-muted-foreground">Google ADK Multi-Agent System Architecture</p>
        </div>
        <Badge variant="outline" className="text-sm">Powered by Gemini 1.5 Pro</Badge>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {agents.map((agent) => (
          <Card key={agent.name}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center text-xl">
                  <agent.icon className="mr-3 h-6 w-6 text-primary" />
                  {agent.name}
                </CardTitle>
                <Badge>{agent.role}</Badge>
              </div>
              <CardDescription className="pt-2">{agent.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <h4 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wider">Available Tools</h4>
              <div className="flex flex-wrap gap-2">
                {agent.tools.map((tool) => (
                  <Badge key={tool} variant="secondary" className="font-mono text-xs">
                    {tool}()
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
