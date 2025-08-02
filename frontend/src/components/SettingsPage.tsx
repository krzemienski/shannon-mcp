import React from 'react'
import { Settings, Server, Key, Bell, Palette } from 'lucide-react'

export function SettingsPage() {
  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Configure your Shannon MCP instance
        </p>
      </div>

      {/* Settings Sections */}
      <div className="space-y-8">
        {/* General */}
        <div className="bg-card rounded-lg border border-border p-6">
          <div className="flex items-center mb-4">
            <Settings className="w-5 h-5 mr-2 text-primary" />
            <h2 className="text-lg font-semibold text-foreground">General</h2>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Server Host
              </label>
              <input
                type="text"
                defaultValue="localhost"
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                WebSocket Port
              </label>
              <input
                type="number"
                defaultValue="8080"
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground"
              />
            </div>
          </div>
        </div>

        {/* Authentication */}
        <div className="bg-card rounded-lg border border-border p-6">
          <div className="flex items-center mb-4">
            <Key className="w-5 h-5 mr-2 text-primary" />
            <h2 className="text-lg font-semibold text-foreground">Authentication</h2>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                JWT Secret Key
              </label>
              <input
                type="password"
                placeholder="Enter your JWT secret key"
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Token Expiry (hours)
              </label>
              <input
                type="number"
                defaultValue="24"
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground"
              />
            </div>
          </div>
        </div>

        {/* MCP Servers */}
        <div className="bg-card rounded-lg border border-border p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <Server className="w-5 h-5 mr-2 text-primary" />
              <h2 className="text-lg font-semibold text-foreground">MCP Servers</h2>
            </div>
            <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors">
              Add Server
            </button>
          </div>
          
          <div className="text-center py-8">
            <Server className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">No MCP servers configured</p>
          </div>
        </div>

        {/* Notifications */}
        <div className="bg-card rounded-lg border border-border p-6">
          <div className="flex items-center mb-4">
            <Bell className="w-5 h-5 mr-2 text-primary" />
            <h2 className="text-lg font-semibold text-foreground">Notifications</h2>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-foreground">Session notifications</p>
                <p className="text-sm text-muted-foreground">Get notified when sessions complete</p>
              </div>
              <input type="checkbox" className="h-4 w-4" defaultChecked />
            </div>
            
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-foreground">Error notifications</p>
                <p className="text-sm text-muted-foreground">Get notified when sessions fail</p>
              </div>
              <input type="checkbox" className="h-4 w-4" defaultChecked />
            </div>
          </div>
        </div>

        {/* Appearance */}
        <div className="bg-card rounded-lg border border-border p-6">
          <div className="flex items-center mb-4">
            <Palette className="w-5 h-5 mr-2 text-primary" />
            <h2 className="text-lg font-semibold text-foreground">Appearance</h2>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Theme
              </label>
              <select className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground">
                <option value="system">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="mt-8 flex justify-end">
        <button className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors">
          Save Settings
        </button>
      </div>
    </div>
  )
}