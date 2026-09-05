"use client"

import { useEffect, useState, useRef } from "react"
import { useParams, useRouter } from "next/navigation"
import { 
  AlertTriangle, 
  ArrowRight,
  CheckCircle2, 
  ChevronRight,
  Clock, 
  Play, 
  Server, 
  ShieldAlert,
  Terminal,
  XCircle,
  Zap
} from "lucide-react"

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getIncident, getWhatIfImpact, approveRemediation, simulateRemediation } from "@/lib/api"

export default function InvestigatePage() {
  const params = useParams()
  const router = useRouter()
  const incidentId = params.id as string
  
  const [incident, setIncident] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  
  // Agent streaming state
  const [events, setEvents] = useState<any[]>([])
  const [isInvestigating, setIsInvestigating] = useState(false)
  const [investigationResult, setInvestigationResult] = useState<any>(null)
  const [streamError, setStreamError] = useState<string | null>(null)
  
  // What If state
  const [whatIfLoading, setWhatIfLoading] = useState(false)
  const [whatIfResult, setWhatIfResult] = useState<any>(null)
  
  // Remediation state
  const [approving, setApproving] = useState<string | null>(null)
  const [simulating, setSimulating] = useState(false)
  const [remediationResult, setRemediationResult] = useState<any>(null)
  
  const eventEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    async function fetchIncident() {
      try {
        const data = await getIncident(incidentId)
        setIncident(data)
        
        // If already investigated, set the result
        if (data.status !== 'ACTIVE' && data.root_cause) {
          setInvestigationResult(data)
        }
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    fetchIncident()
  }, [incidentId])

  useEffect(() => {
    // Auto-scroll agent events
    if (eventEndRef.current) {
      eventEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events])

  const startInvestigation = () => {
    setIsInvestigating(true)
    setEvents([])
    setStreamError(null)
    
    try {
      const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/agent/investigate`
      
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ incident_id: incidentId })
      }).then(async response => {
        if (!response.ok || !response.body) {
          throw new Error('Failed to start investigation stream')
        }
        
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          
          const chunk = decoder.decode(value, { stream: true })
          const lines = chunk.split('\n\n')
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                
                if (data.event_type === 'DONE') {
                  setIsInvestigating(false)
                  // Reload incident to get full data
                  const updated = await getIncident(incidentId)
                  setIncident(updated)
                  setInvestigationResult(updated)
                } else if (data.event_type === 'INVESTIGATION_RESULT' && data.data?.result) {
                  setInvestigationResult(data.data.result)
                  setEvents(prev => [...prev, data])
                } else if (data.event_type === 'ERROR') {
                  setStreamError(data.message)
                  setIsInvestigating(false)
                  setEvents(prev => [...prev, data])
                } else {
                  setEvents(prev => [...prev, data])
                }
              } catch (e) {
                console.error('Error parsing SSE:', e)
              }
            }
          }
        }
      }).catch(err => {
        setStreamError(err.message)
        setIsInvestigating(false)
      })
    } catch (err: any) {
      setStreamError(err.message)
      setIsInvestigating(false)
    }
  }

  const handleWhatIf = async () => {
    setWhatIfLoading(true)
    try {
      const result = await getWhatIfImpact(incidentId)
      setWhatIfResult(result)
    } catch (err) {
      console.error(err)
    } finally {
      setWhatIfLoading(false)
    }
  }

  const handleApproveRemediation = async (actionId: string) => {
    setApproving(actionId)
    try {
      // Approve
      await approveRemediation(actionId)
      
      // Simulate execution automatically for the demo
      setSimulating(true)
      const result = await simulateRemediation(actionId)
      setRemediationResult(result)
      
      // Refresh incident
      const updated = await getIncident(incidentId)
      setIncident(updated)
      
    } catch (err) {
      console.error(err)
      alert("Remediation failed")
    } finally {
      setApproving(null)
      setSimulating(false)
    }
  }

  if (loading) {
    return <div className="flex h-[50vh] items-center justify-center">Loading incident...</div>
  }

  if (!incident) {
    return <div className="flex h-[50vh] items-center justify-center">Incident not found</div>
  }

  const isResolved = incident.status === 'RESOLVED' || incident.status === 'CLOSED'
  const hasResult = !!investigationResult

  return (
    <div className="space-y-8 pb-12 animate-in fade-in duration-500">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-6">
        <div>
          <div className="flex items-center space-x-2 mb-2">
            <h1 className="text-3xl font-bold tracking-tight">{incident.title}</h1>
            <Badge variant={isResolved ? "success" : "destructive"} className="text-sm">
              {incident.status}
            </Badge>
          </div>
          <p className="text-muted-foreground">{incident.description}</p>
        </div>
        
        {!hasResult && !isInvestigating && (
          <Button size="lg" variant="destructive" onClick={startInvestigation} className="animate-pulse">
            <Play className="mr-2 h-5 w-5" /> INVESTIGATE WITH AGENT
          </Button>
        )}
      </div>

      {/* Agent Activity Stream */}
      {(isInvestigating || (events.length > 0 && !hasResult)) && (
        <Card className="border-primary/50 shadow-md">
          <CardHeader className="bg-secondary/30 pb-4">
            <CardTitle className="flex items-center text-lg">
              <Terminal className="mr-2 h-5 w-5 text-primary" />
              Agent Investigation Activity
              {isInvestigating && <span className="ml-3 flex h-2 w-2 rounded-full bg-primary animate-ping" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="max-h-[300px] overflow-y-auto p-4 space-y-3 font-mono text-sm bg-black/50 text-gray-300">
              {events.map((event, i) => (
                <div key={i} className="flex items-start">
                  <span className="text-muted-foreground mr-3 shrink-0">
                    {new Date(event.timestamp).toLocaleTimeString([], {hour12: false})}
                  </span>
                  <div>
                    {event.success === false ? (
                      <span className="text-red-400">✗ {event.message}</span>
                    ) : event.event_type === 'TOOL_CALL' ? (
                      <span className="text-blue-300">▶ {event.message}</span>
                    ) : (
                      <span className="text-green-400">✓ {event.message}</span>
                    )}
                    {event.tool_name && (
                      <span className="ml-2 text-xs text-muted-foreground">[{event.tool_name}]</span>
                    )}
                  </div>
                </div>
              ))}
              {streamError && (
                <div className="text-red-500 mt-2">Stream error: {streamError}</div>
              )}
              {isInvestigating && (
                <div className="flex items-center text-primary mt-2">
                  <span className="animate-pulse">_</span>
                </div>
              )}
              <div ref={eventEndRef} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results Section */}
      {hasResult && (
        <div className="grid gap-6 md:grid-cols-2 animate-in slide-in-from-bottom-4 duration-700">
          
          {/* Root Cause Card */}
          <Card className="md:col-span-2 border-l-4 border-l-destructive">
            <CardHeader>
              <CardTitle className="flex items-center">
                <AlertTriangle className="mr-2 h-5 w-5 text-destructive" />
                Root Cause Analysis
              </CardTitle>
              <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                <span>Confidence:</span>
                <span className="font-bold text-foreground">
                  {Math.round((investigationResult.confidence || 0) * 100)}%
                </span>
                <span>•</span>
                <span>System: {investigationResult.root_cause_system}</span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-lg font-medium mb-6">
                {investigationResult.root_cause}
              </p>
              
              <h4 className="font-semibold mb-3 text-sm uppercase text-muted-foreground">Supporting Evidence</h4>
              <div className="space-y-3">
                {investigationResult.evidence?.map((item: any, i: number) => (
                  <div key={i} className="flex justify-between items-center p-3 rounded-md bg-secondary/30">
                    <div className="flex items-center">
                      <Server className="h-4 w-4 mr-2 text-muted-foreground" />
                      <span className="font-mono text-sm">{item.metric}</span>
                    </div>
                    <div className="flex items-center space-x-4 text-sm">
                      <span className="text-muted-foreground">
                        {item.current_value} (vs {item.baseline_value})
                      </span>
                      {item.status === 'ANOMALOUS' ? (
                        <Badge variant="destructive" className="w-24 justify-center">ANOMALOUS</Badge>
                      ) : (
                        <Badge variant="outline" className="w-24 justify-center">NORMAL</Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Production Impact Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <ShieldAlert className="mr-2 h-5 w-5 text-yellow-500" />
                Production Impact
              </CardTitle>
              <CardDescription>Scene {(investigationResult.affected_scene_numbers || [])[0]} Editorial Deadline</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {investigationResult.production_impact && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-secondary/30 rounded-md">
                      <div className="text-xs text-muted-foreground mb-1">Current Ingest</div>
                      <div className="font-bold text-red-400">
                        {investigationResult.production_impact.current_ingest_rate_gbps} GB/s
                      </div>
                    </div>
                    <div className="p-3 bg-secondary/30 rounded-md">
                      <div className="text-xs text-muted-foreground mb-1">Required Ingest</div>
                      <div className="font-bold">
                        {investigationResult.production_impact.required_ingest_rate_gbps} GB/s
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-2 pt-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Projected Delay</span>
                      <span className="font-bold text-red-400">
                        ~{investigationResult.production_impact.projected_delay_minutes} minutes
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Deadline At Risk</span>
                      <span className="font-bold">
                        {investigationResult.production_impact.deadline_at_risk ? 'YES' : 'NO'}
                      </span>
                    </div>
                  </div>
                </>
              )}

              {!whatIfResult && !isResolved && (
                <Button variant="outline" className="w-full mt-4" onClick={handleWhatIf} disabled={whatIfLoading}>
                  {whatIfLoading ? "Calculating..." : "What if we do nothing?"}
                </Button>
              )}

              {whatIfResult && (
                <div className="mt-4 p-4 border border-destructive/50 rounded-md bg-destructive/5 animate-in slide-in-from-top-2">
                  <h4 className="font-semibold text-destructive flex items-center mb-3">
                    <Clock className="mr-2 h-4 w-4" /> Projected Consequences
                  </h4>
                  <div className="space-y-3 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-destructive/30 before:to-transparent">
                    {whatIfResult.projections.map((proj: any, i: number) => (
                      <div key={i} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                        <div className="flex items-center justify-center w-10 h-10 rounded-full border border-white/20 bg-background text-destructive text-xs font-bold shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10">
                          {proj.time_minutes}m
                        </div>
                        <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-3 rounded bg-secondary/50 border border-secondary">
                          <div className="font-semibold text-sm">{proj.event}</div>
                          <div className="text-xs text-muted-foreground mt-1">{proj.description}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Remediation Card */}
          <Card className={isResolved ? "border-success/50 bg-success/5" : ""}>
            <CardHeader>
              <CardTitle className="flex items-center">
                {isResolved ? (
                  <CheckCircle2 className="mr-2 h-5 w-5 text-green-500" />
                ) : (
                  <Zap className="mr-2 h-5 w-5 text-blue-400" />
                )}
                Remediation Recommendations
              </CardTitle>
              <CardDescription>
                {isResolved 
                  ? "Incident has been resolved and verified." 
                  : "Generated by agent based on root cause analysis. Requires approval."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {remediationResult && (
                <div className="mb-6 p-4 border border-green-500/30 bg-green-500/10 rounded-md text-sm animate-in zoom-in-95">
                  <div className="font-bold text-green-500 mb-2 flex items-center">
                    <CheckCircle2 className="h-4 w-4 mr-2" /> RECOVERY VERIFIED
                  </div>
                  <div className="space-y-1 text-muted-foreground">
                    <div>{remediationResult.verification?.summary}</div>
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      <div>Storage: {remediationResult.telemetry_changes?.storage_utilization?.before} → <span className="text-green-500 font-bold">{remediationResult.telemetry_changes?.storage_utilization?.after}</span></div>
                      <div>Ingest: {remediationResult.telemetry_changes?.ingest_throughput_gbps?.before} → <span className="text-green-500 font-bold">{remediationResult.telemetry_changes?.ingest_throughput_gbps?.after}</span></div>
                    </div>
                  </div>
                </div>
              )}

              <div className="space-y-4">
                {(investigationResult.recommended_actions || incident.recommended_actions || []).map((action: any, i: number) => {
                  const isSimulating = approving === action.id || simulating
                  return (
                    <div key={i} className="p-4 rounded-md border bg-card">
                      <div className="flex justify-between items-start mb-2">
                        <div className="font-medium">{i+1}. {action.action}</div>
                      </div>
                      <div className="flex gap-3 text-xs mb-4">
                        <Badge variant="outline" className="font-normal">Risk: {action.risk_level}</Badge>
                        <Badge variant="outline" className="font-normal text-blue-400 border-blue-900/50">Benefit: {action.expected_benefit}</Badge>
                        <span className="text-muted-foreground flex items-center">
                          <Clock className="h-3 w-3 mr-1" /> ~{action.expected_recovery_minutes}m recovery
                        </span>
                      </div>
                      
                      {!isResolved && (
                        <div className="flex gap-2">
                          <Button 
                            size="sm" 
                            className="bg-blue-600 hover:bg-blue-700" 
                            onClick={() => handleApproveRemediation(action.id || `action-${i+1}`)}
                            disabled={isSimulating}
                          >
                            {isSimulating ? 'Simulating...' : 'Approve & Simulate'}
                          </Button>
                          <Button size="sm" variant="ghost" disabled={isSimulating}>Reject</Button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>

        </div>
      )}
    </div>
  )
}
