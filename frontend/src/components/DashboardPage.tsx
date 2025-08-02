import React from 'react'
import { Link } from 'react-router-dom'
import { 
  Plus, 
  Activity, 
  Clock, 
  Zap,
  MessageSquare,
  Users,
  Cpu
} from 'lucide-react'
import { useSessionStore } from '@/stores/sessionStore'

export function DashboardPage() {
  const sessions = useSessionStore(state => state.sessions)
  const connected = useSessionStore(state => state.connected)
  
  const activeSessions = Object.values(sessions).filter(s => s.state === 'running')
  const totalSessions = Object.keys(sessions).length

  const stats = [
    {
      name: 'Active Sessions',
      value: activeSessions.length.toString(),
      icon: Activity,
      color: 'text-green-600'
    },
    {
      name: 'Total Sessions',
      value: totalSessions.toString(),
      icon: MessageSquare,
      color: 'text-blue-600'
    },
    {
      name: 'Agents',
      value: '0',
      icon: Users,
      color: 'text-purple-600'
    },
    {
      name: 'MCP Servers',
      value: '0',
      icon: Cpu,
      color: 'text-orange-600'
    }
  ]

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
            <p className="text-muted-foreground mt-1">
              Manage your Claude Code sessions and MCP servers
            </p>
          </div>
          
          <Link
            to="/session"
            className="inline-flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Session
          </Link>
        </div>
      </div>

      {/* Connection Status */}
      <div className="mb-8">
        <div className={`p-4 rounded-lg border ${
          connected 
            ? 'bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800' 
            : 'bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-800'
        }`}>
          <div className="flex items-center">
            <div className={`w-3 h-3 rounded-full mr-3 ${
              connected ? 'bg-green-500' : 'bg-red-500'
            }`} />
            <span className={`font-medium ${
              connected ? 'text-green-800 dark:text-green-200' : 'text-red-800 dark:text-red-200'
            }`}>
              {connected ? 'Connected to Shannon MCP Server' : 'Disconnected from Server'}
            </span>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {stats.map((stat) => (
          <div key={stat.name} className="bg-card p-6 rounded-lg border border-border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{stat.name}</p>
                <p className="text-2xl font-bold text-foreground mt-1">{stat.value}</p>
              </div>
              <stat.icon className={`w-8 h-8 ${stat.color}`} />
            </div>
          </div>
        ))}
      </div>

      {/* Recent Sessions */}
      <div className="bg-card rounded-lg border border-border">
        <div className="p-6 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">Recent Sessions</h2>
        </div>
        
        <div className="p-6">
          {totalSessions === 0 ? (
            <div className="text-center py-12">
              <MessageSquare className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium text-foreground mb-2">No sessions yet</h3>
              <p className="text-muted-foreground mb-6">
                Start your first Claude Code session to see it here
              </p>
              <Link
                to="/session"
                className="inline-flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Session
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              {Object.values(sessions).slice(0, 5).map((session) => (
                <div key={session.id} className="flex items-center justify-between p-4 bg-muted rounded-lg">
                  <div className="flex items-center space-x-4">
                    <div className={`w-3 h-3 rounded-full ${
                      session.state === 'running' ? 'bg-green-500' : 
                      session.state === 'completed' ? 'bg-blue-500' : 
                      session.state === 'failed' ? 'bg-red-500' : 'bg-gray-500'
                    }`} />
                    <div>
                      <p className="font-medium text-foreground">{session.id}</p>
                      <p className="text-sm text-muted-foreground">
                        {session.model} • {new Date(session.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <p className="text-sm font-medium text-foreground">
                        {session.metrics.tokens_input + session.metrics.tokens_output} tokens
                      </p>
                      <p className="text-sm text-muted-foreground capitalize">
                        {session.state}
                      </p>
                    </div>
                    <Link
                      to={`/session/${session.id}`}
                      className="px-3 py-1 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/90 transition-colors"
                    >
                      View
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}