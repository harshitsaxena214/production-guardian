"use client"

import { useEffect, useState } from "react"
import { AlertCircle, RefreshCw, Activity, Terminal } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getTelemetryStatus, simulateIncident, resetDemo, getGrafanaStatus } from "@/lib/api"

export default function TelemetryPage() {
  const [status, setStatus] = useState<any>(null)
  const [grafanaStatus, setGrafanaStatus] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [simulating, setSimulating] = useState(false)
  const [resetting, setResetting] = useState(false)

  const fetchData = async () => {
    try {
      const [telData, grafData] = await Promise.all([
        getTelemetryStatus(),
        getGrafanaStatus().catch(() => ({ mcp_available: false, message: "Connection failed" }))
      ])
      setStatus(telData)
      setGrafanaStatus(grafData)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 3000)
    return () => clearInterval(interval)
  }, [])

  const handleSimulate = async (scenario: string) => {
    setSimulating(true)
    try {
      await simulateIncident(scenario)
      await fetchData()
    } catch (err) {
      console.error(err)
      alert("Failed to simulate incident")
    } finally {
      setSimulating(false)
    }
  }

  const handleReset = async () => {
    setResetting(true)
    try {
      await resetDemo()
      await fetchData()
    } catch (err) {
      console.error(err)
      alert("Failed to reset demo")
    } finally {
      setResetting(false)
    }
  }

  const scenarios = [
    {
      id: "STORAGE_SATURATION",
      name: "Storage Saturation",
      desc: "Disk fills up causing I/O contention and dropped throughput.",
      target: "INGEST-01"
    },
    {
      id: "NETWORK_DEGRADATION",
      name: "Network Degradation",
      desc: "Packet loss and latency spike on edge network.",
      target: "NET-EDGE-07"
    },
    {
      id: "CAMERA_FAILURE",
      name: "Camera Overheat",
      desc: "Thermal event causing recording errors and dropped frames.",
      target: "CAM-03"
    },
    {
      id: "RENDER_BOTTLENECK",
      name: "Render Bottleneck",
      desc: "GPU saturation causing queue buildup.",
      target: "EDIT-01"
    }
  ]

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Telemetry & Control</h1>
          <p className="text-muted-foreground">Manage the synthetic environment and Grafana integration</p>
        </div>
        <Button 
          variant="outline" 
          onClick={handleReset} 
          disabled={resetting || !status?.incident_active}
        >
          {resetting ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
          Reset Demo
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Activity className="mr-2 h-5 w-5" />
              Simulator Engine
            </CardTitle>
            <CardDescription>Current state of the synthetic environment</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between border-b pb-2">
              <span className="text-muted-foreground">State</span>
              <Badge variant={status?.incident_active ? "destructive" : "success"}>
                {status?.simulator_state || "UNKNOWN"}
              </Badge>
            </div>
            <div className="flex justify-between border-b pb-2">
              <span className="text-muted-foreground">Active Scenario</span>
              <span className="font-medium">{status?.scenario || "None"}</span>
            </div>
            <div className="flex justify-between pb-2">
              <span className="text-muted-foreground">Data Source</span>
              <Badge variant="outline">{status?.data_source || "N/A"}</Badge>
            </div>
            
            {status?.incident_active && (
              <div className="mt-4 rounded-md bg-destructive/10 p-4">
                <div className="flex items-start">
                  <AlertCircle className="mr-2 h-5 w-5 text-destructive" />
                  <div>
                    <h4 className="font-semibold text-destructive">Incident is active</h4>
                    <p className="text-sm text-destructive/80">
                      Telemetry is currently degraded and being pushed to Grafana.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Terminal className="mr-2 h-5 w-5" />
              Grafana MCP Integration
            </CardTitle>
            <CardDescription>Connection to the Model Context Protocol server</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between border-b pb-2">
              <span className="text-muted-foreground">Status</span>
              <Badge variant={grafanaStatus?.mcp_available ? "success" : "destructive"}>
                {grafanaStatus?.mcp_available ? "CONNECTED" : "UNAVAILABLE"}
              </Badge>
            </div>
            <div className="flex justify-between border-b pb-2">
              <span className="text-muted-foreground">MCP URL</span>
              <span className="text-sm font-mono">{grafanaStatus?.mcp_url || "Not configured"}</span>
            </div>
            <div className="flex justify-between pb-2">
              <span className="text-muted-foreground">Available Tools</span>
              <span className="font-medium">{grafanaStatus?.tools_available?.length || 0}</span>
            </div>

            {!grafanaStatus?.mcp_available && (
              <div className="mt-4 rounded-md bg-yellow-500/10 p-4">
                <p className="text-sm text-yellow-500 font-medium">
                  Agents will fall back to local simulator data for investigation.
                </p>
                <p className="text-xs text-yellow-500/80 mt-1">
                  Start the mcp-grafana server to enable real tool calls.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <h2 className="text-2xl font-bold tracking-tight mt-10">Incident Simulator</h2>
      <p className="text-muted-foreground mb-6">Trigger specific infrastructure incidents to test the agent's diagnostic capabilities.</p>

      <div className="grid gap-4 md:grid-cols-2">
        {scenarios.map((scenario) => (
          <Card key={scenario.id} className={status?.scenario === scenario.id ? "border-destructive shadow-md" : ""}>
            <CardHeader>
              <div className="flex justify-between">
                <CardTitle>{scenario.name}</CardTitle>
                <Badge variant="outline">{scenario.target}</Badge>
              </div>
              <CardDescription>{scenario.desc}</CardDescription>
            </CardHeader>
            <CardFooter>
              <Button 
                onClick={() => handleSimulate(scenario.id)} 
                disabled={simulating || status?.incident_active}
                variant={status?.scenario === scenario.id ? "destructive" : "default"}
                className="w-full"
              >
                {status?.scenario === scenario.id ? "Currently Active" : "Simulate Incident"}
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  )
}
