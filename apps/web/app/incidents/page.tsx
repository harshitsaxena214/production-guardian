"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { AlertTriangle, ChevronRight, Clock, ShieldAlert } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getIncidents } from "@/lib/api"

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchIncidents() {
      try {
        const data = await getIncidents()
        setIncidents(data)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    fetchIncidents()
    const interval = setInterval(fetchIncidents, 5000)
    return () => clearInterval(interval)
  }, [])

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return <Badge variant="destructive">{severity}</Badge>
      case 'HIGH': return <Badge variant="warning" className="bg-orange-500/15 text-orange-500">{severity}</Badge>
      case 'MEDIUM': return <Badge variant="warning">{severity}</Badge>
      default: return <Badge variant="secondary">{severity}</Badge>
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ACTIVE': return <Badge variant="destructive" className="animate-pulse">ACTIVE</Badge>
      case 'INVESTIGATING': return <Badge variant="warning">INVESTIGATING</Badge>
      case 'REMEDIATING': return <Badge className="bg-blue-500/15 text-blue-500 hover:bg-blue-500/25 border-transparent">REMEDIATING</Badge>
      case 'RESOLVED': return <Badge variant="success">RESOLVED</Badge>
      case 'CLOSED': return <Badge variant="outline">CLOSED</Badge>
      default: return <Badge>{status}</Badge>
    }
  }

  if (loading && incidents.length === 0) {
    return <div className="flex h-[50vh] items-center justify-center">Loading incidents...</div>
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Incidents</h1>
          <p className="text-muted-foreground">Production infrastructure anomalies and alerts</p>
        </div>
      </div>

      {incidents.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <ShieldAlert className="mb-4 h-12 w-12 text-muted-foreground/50" />
            <h3 className="mb-2 text-lg font-medium">No Incidents Found</h3>
            <p className="mb-6 text-sm text-muted-foreground">All systems are currently operating normally.</p>
            <Link href="/telemetry">
              <Button>Go to Simulator</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {incidents.map((incident) => (
            <Card key={incident.id} className={`transition-all hover:shadow-md ${incident.status === 'ACTIVE' ? 'border-destructive/50' : ''}`}>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between p-6">
                <div className="flex-1 space-y-1">
                  <div className="flex items-center space-x-2">
                    {incident.status === 'ACTIVE' && <AlertTriangle className="h-4 w-4 text-destructive" />}
                    <h3 className="font-semibold text-lg">{incident.title}</h3>
                  </div>
                  <div className="flex flex-wrap gap-2 pt-2">
                    {getStatusBadge(incident.status)}
                    {getSeverityBadge(incident.severity)}
                    <Badge variant="outline" className="flex items-center">
                      <Clock className="mr-1 h-3 w-3" />
                      {new Date(incident.started_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                    </Badge>
                    {incident.deadline_at_risk && (
                      <Badge variant="destructive" className="bg-red-900/40 text-red-400 border-red-900">
                        DEADLINE AT RISK
                      </Badge>
                    )}
                  </div>
                </div>
                
                <div className="mt-4 sm:mt-0 flex items-center space-x-4">
                  {incident.status === 'ACTIVE' ? (
                    <Link href={`/incidents/${incident.id}/investigate`}>
                      <Button variant="destructive">
                        Investigate with Agent
                      </Button>
                    </Link>
                  ) : (
                    <Link href={`/incidents/${incident.id}/investigate`}>
                      <Button variant="secondary">
                        View Details <ChevronRight className="ml-2 h-4 w-4" />
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
