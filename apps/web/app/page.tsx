"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { 
  Activity, 
  AlertTriangle, 
  Camera, 
  CheckCircle2, 
  Clock, 
  Database, 
  HardDrive, 
  Network, 
  Server, 
  Video
} from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { getProductionOverview } from "@/lib/api"

export default function OverviewPage() {
  const [overview, setOverview] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    async function fetchData() {
      try {
        const data = await getProductionOverview()
        setOverview(data)
      } catch (err: any) {
        setError(err.message || "Failed to load production data")
      } finally {
        setLoading(false)
      }
    }
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  if (loading && !overview) {
    return <div className="flex h-[50vh] items-center justify-center">Loading production data...</div>
  }

  if (error && !overview) {
    return (
      <div className="flex h-[50vh] flex-col items-center justify-center space-y-4">
        <AlertTriangle className="h-12 w-12 text-destructive" />
        <h2 className="text-xl font-bold">Failed to load data</h2>
        <p className="text-muted-foreground">{error}</p>
        <p className="text-sm text-muted-foreground">Make sure the backend is running and seeded.</p>
      </div>
    )
  }

  const { production, system_health, active_incident_count, current_scene } = overview

  const healthItems = [
    { name: "Cameras", score: system_health.cameras, icon: Camera },
    { name: "Ingest", score: system_health.ingest, icon: Server },
    { name: "Storage", score: system_health.storage, icon: HardDrive },
    { name: "Network", score: system_health.network, icon: Network },
    { name: "Editing", score: system_health.editing, icon: Video },
  ]

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{production.display_name}</h1>
          <p className="text-muted-foreground">
            Production Day {production.production_day} • {production.primary_location}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {active_incident_count > 0 ? (
            <Badge variant="destructive" className="h-8 px-3 text-sm animate-pulse">
              {active_incident_count} ACTIVE INCIDENT{active_incident_count > 1 ? 'S' : ''}
            </Badge>
          ) : (
            <Badge variant="success" className="h-8 px-3 text-sm">
              <CheckCircle2 className="mr-2 h-4 w-4" /> ALL SYSTEMS NORMAL
            </Badge>
          )}
        </div>
      </div>

      {active_incident_count > 0 && (
        <Card className="border-destructive bg-destructive/10">
          <CardHeader>
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              <CardTitle className="text-destructive">Critical Incident Detected</CardTitle>
            </div>
            <CardDescription className="text-destructive/80">
              An infrastructure incident is actively threatening production.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link 
              href="/incidents" 
              className="inline-flex h-9 items-center justify-center rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground shadow hover:bg-destructive/90"
            >
              View Active Incidents
            </Link>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle>Current Scene Context</CardTitle>
            <CardDescription>What the production is actively shooting</CardDescription>
          </CardHeader>
          <CardContent>
            {current_scene ? (
              <div className="space-y-6">
                <div className="flex justify-between">
                  <div>
                    <h3 className="text-2xl font-bold">Scene {current_scene.scene_number}: {current_scene.title}</h3>
                    <p className="text-muted-foreground">{current_scene.description}</p>
                  </div>
                  <Badge variant={current_scene.priority === 'CRITICAL' ? 'destructive' : 'default'} className="h-fit">
                    {current_scene.priority} PRIORITY
                  </Badge>
                </div>

                <div className="grid grid-cols-2 gap-4 rounded-lg border bg-secondary/50 p-4 lg:grid-cols-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Location</p>
                    <p className="font-medium">{current_scene.location}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Estimated Data</p>
                    <p className="font-medium">{current_scene.estimated_footage_gb} GB</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Editorial Deadline</p>
                    <p className="flex items-center font-medium text-yellow-500">
                      <Clock className="mr-1 h-4 w-4" />
                      {current_scene.editorial_deadline}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Dependencies</p>
                    <p className="font-medium">
                      {current_scene.dependent_scene_numbers.map((n: number) => `Scene ${n}`).join(', ')}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-muted-foreground">No active scene data available.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>System Health</CardTitle>
            <CardDescription>Overall infrastructure status</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="mb-6 flex items-center justify-between">
              <span className="text-sm font-medium">Overall Status</span>
              <span className={`text-2xl font-bold ${system_health.overall > 90 ? 'text-green-500' : system_health.overall > 70 ? 'text-yellow-500' : 'text-red-500'}`}>
                {system_health.overall.toFixed(1)}%
              </span>
            </div>
            
            <div className="space-y-4">
              {healthItems.map((item) => (
                <div key={item.name} className="flex items-center">
                  <div className="flex w-24 items-center text-sm text-muted-foreground">
                    <item.icon className="mr-2 h-4 w-4" />
                    {item.name}
                  </div>
                  <div className="ml-4 flex-1">
                    <Progress 
                      value={item.score} 
                      indicatorClassName={
                        item.score > 90 ? 'bg-green-500' : 
                        item.score > 70 ? 'bg-yellow-500' : 'bg-red-500'
                      }
                    />
                  </div>
                  <div className="ml-4 w-12 text-right text-sm font-medium">
                    {item.score}%
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
