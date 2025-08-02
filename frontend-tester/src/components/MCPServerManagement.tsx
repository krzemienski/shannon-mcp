import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Typography, 
  Button, 
  Grid, 
  Paper, 
  TextField,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Alert,
  Chip,
  Card,
  CardContent,
  Tabs,
  Tab,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Badge,
  Tooltip,
  Divider
} from '@mui/material';
import { 
  Add,
  Terminal,
  Language as Globe,
  Delete,
  PlayArrow,
  CheckCircle,
  Refresh,
  FolderOpen,
  Person,
  Article,
  ExpandMore as ChevronDown,
  ExpandLess as ChevronUp,
  ContentCopy,
  Download,
  Upload,
  Settings,
  NetworkCheck
} from '@mui/icons-material';
import ReactJson from 'react-json-view';
import MonacoEditor from '@monaco-editor/react';
import MCPClient from '../services/MCPClient';

interface MCPServerManagementProps {
  client: MCPClient;
}

interface MCPServer {
  name: string;
  transport: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  scope: string;
  isActive?: boolean;
  status?: {
    running: boolean;
    error?: string;
    lastChecked?: string;
  };
}

const MCPServerManagement: React.FC<MCPServerManagementProps> = ({ client }) => {
  const [loading, setLoading] = useState<string | null>(null);
  const [response, setResponse] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  const [expandedServers, setExpandedServers] = useState<Set<string>>(new Set());
  
  // Dialog states
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [addJsonDialogOpen, setAddJsonDialogOpen] = useState(false);
  
  // Form states for stdio server
  const [stdioForm, setStdioForm] = useState({
    name: '',
    command: '',
    args: '',
    scope: 'local',
    env: '{}'
  });
  
  // Form states for SSE server
  const [sseForm, setSseForm] = useState({
    name: '',
    url: '',
    scope: 'local',
    env: '{}'
  });
  
  // JSON configuration for add_json
  const [jsonConfig, setJsonConfig] = useState({
    name: '',
    config: JSON.stringify({
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-example'],
      env: {}
    }, null, 2),
    scope: 'local'
  });

  useEffect(() => {
    handleListServers();
  }, []);

  const handleToolCall = async (toolName: string, params?: any) => {
    setLoading(toolName);
    setError(null);
    try {
      let result;
      switch (toolName) {
        case 'mcp_add':
          result = await client.mcpAdd(params);
          setAddDialogOpen(false);
          handleListServers();
          break;
        case 'mcp_list':
          result = await client.mcpList();
          setServers(result || []);
          break;
        case 'mcp_add_json':
          result = await client.mcpAddJson(params);
          setAddJsonDialogOpen(false);
          handleListServers();
          break;
        case 'mcp_add_from_claude_desktop':
          result = await client.mcpAddFromClaudeDesktop();
          handleListServers();
          break;
        case 'mcp_serve':
          result = await client.mcpServe();
          break;
        case 'mcp_remove':
          if (window.confirm(`Remove MCP server "${params.name}"?`)) {
            result = await client.mcpRemove(params.name);
            handleListServers();
          }
          break;
      }
      setResponse(result);
    } catch (err: any) {
      setError(err.message || 'Unknown error occurred');
    } finally {
      setLoading(null);
    }
  };

  const handleListServers = () => {
    handleToolCall('mcp_list');
  };

  const handleAddStdioServer = () => {
    try {
      const args = stdioForm.args.trim() ? stdioForm.args.split(/\s+/) : [];
      const env = JSON.parse(stdioForm.env);
      
      handleToolCall('mcp_add', {
        name: stdioForm.name,
        transport: 'stdio',
        command: stdioForm.command,
        args,
        env,
        scope: stdioForm.scope
      });
    } catch (err) {
      setError('Invalid JSON in environment field');
    }
  };

  const handleAddSseServer = () => {
    try {
      const env = JSON.parse(sseForm.env);
      
      handleToolCall('mcp_add', {
        name: sseForm.name,
        transport: 'sse',
        url: sseForm.url,
        env,
        scope: sseForm.scope
      });
    } catch (err) {
      setError('Invalid JSON in environment field');
    }
  };

  const handleAddJsonServer = () => {
    try {
      JSON.parse(jsonConfig.config); // Validate JSON
      handleToolCall('mcp_add_json', {
        name: jsonConfig.name,
        jsonConfig: jsonConfig.config,
        scope: jsonConfig.scope
      });
    } catch (err) {
      setError('Invalid JSON configuration');
    }
  };

  const toggleExpanded = (serverName: string) => {
    setExpandedServers(prev => {
      const next = new Set(prev);
      if (next.has(serverName)) {
        next.delete(serverName);
      } else {
        next.add(serverName);
      }
      return next;
    });
  };

  const getTransportIcon = (transport: string) => {
    switch (transport) {
      case 'stdio':
        return <Terminal className="h-4 w-4" style={{ color: '#FFA500' }} />;
      case 'sse':
        return <Globe className="h-4 w-4" style={{ color: '#10B981' }} />;
      default:
        return <NetworkCheck className="h-4 w-4" style={{ color: '#3B82F6' }} />;
    }
  };

  const getScopeIcon = (scope: string) => {
    switch (scope) {
      case 'local':
        return <Person className="h-3 w-3" style={{ color: '#6B7280' }} />;
      case 'project':
        return <FolderOpen className="h-3 w-3" style={{ color: '#FB923C' }} />;
      case 'user':
        return <Article className="h-3 w-3" style={{ color: '#A855F7' }} />;
      default:
        return null;
    }
  };

  const renderServerItem = (server: MCPServer) => {
    const isExpanded = expandedServers.has(server.name);
    
    return (
      <Card key={server.name} sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
            <Box sx={{ flex: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                {getTransportIcon(server.transport)}
                <Typography variant="h6" component="span">
                  {server.name}
                </Typography>
                <Chip 
                  label={server.transport} 
                  size="small" 
                  variant="outlined"
                />
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  {getScopeIcon(server.scope)}
                  <Chip 
                    label={server.scope} 
                    size="small" 
                    variant="outlined"
                  />
                </Box>
                {server.isActive && (
                  <Chip 
                    label="Active" 
                    size="small" 
                    color="success"
                    icon={<CheckCircle />}
                  />
                )}
              </Box>
              
              {server.command && (
                <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                  {server.command} {server.args?.join(' ')}
                </Typography>
              )}
              
              {server.url && (
                <Typography variant="body2" color="text.secondary">
                  {server.url}
                </Typography>
              )}
              
              <Box sx={{ mt: 1 }}>
                <IconButton
                  size="small"
                  onClick={() => toggleExpanded(server.name)}
                >
                  {isExpanded ? <ChevronUp /> : <ChevronDown />}
                </IconButton>
              </Box>
              
              {isExpanded && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Configuration Details
                  </Typography>
                  <ReactJson 
                    src={server} 
                    theme="monokai" 
                    collapsed={false}
                    displayDataTypes={false}
                  />
                </Box>
              )}
            </Box>
            
            <Box>
              <Tooltip title="Remove Server">
                <IconButton
                  onClick={() => handleToolCall('mcp_remove', { name: server.name })}
                  disabled={loading === 'mcp_remove'}
                  color="error"
                >
                  <Delete />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
        </CardContent>
      </Card>
    );
  };

  // Group servers by scope
  const serversByScope = servers.reduce((acc, server) => {
    const scope = server.scope || 'local';
    if (!acc[scope]) acc[scope] = [];
    acc[scope].push(server);
    return acc;
  }, {} as Record<string, MCPServer[]>);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        MCP Server Management
      </Typography>
      
      <Grid container spacing={3}>
        {/* Tool Buttons */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Grid container spacing={2}>
              <Grid item>
                <Button
                  variant="contained"
                  startIcon={<Add />}
                  onClick={() => setAddDialogOpen(true)}
                  disabled={loading === 'mcp_add'}
                >
                  Add Server
                </Button>
              </Grid>
              <Grid item>
                <Button
                  variant="contained"
                  startIcon={<Settings />}
                  onClick={() => setAddJsonDialogOpen(true)}
                  disabled={loading === 'mcp_add_json'}
                >
                  Add from JSON
                </Button>
              </Grid>
              <Grid item>
                <Button
                  variant="contained"
                  startIcon={<Download />}
                  onClick={() => handleToolCall('mcp_add_from_claude_desktop')}
                  disabled={loading === 'mcp_add_from_claude_desktop'}
                >
                  {loading === 'mcp_add_from_claude_desktop' ? <CircularProgress size={24} /> : 'Import from Claude Desktop'}
                </Button>
              </Grid>
              <Grid item>
                <Button
                  variant="contained"
                  startIcon={<PlayArrow />}
                  onClick={() => handleToolCall('mcp_serve')}
                  disabled={loading === 'mcp_serve'}
                >
                  {loading === 'mcp_serve' ? <CircularProgress size={24} /> : 'Start MCP Server'}
                </Button>
              </Grid>
              <Grid item>
                <Button
                  variant="outlined"
                  startIcon={<Refresh />}
                  onClick={handleListServers}
                  disabled={loading === 'mcp_list'}
                >
                  Refresh
                </Button>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Servers List */}
        {servers.length > 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Configured Servers ({servers.length})
              </Typography>
              
              {Object.entries(serversByScope).map(([scope, scopeServers]) => (
                <Box key={scope} sx={{ mb: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    {getScopeIcon(scope)}
                    <Typography variant="subtitle1">
                      {scope.charAt(0).toUpperCase() + scope.slice(1)} Scope ({scopeServers.length})
                    </Typography>
                  </Box>
                  {scopeServers.map(renderServerItem)}
                </Box>
              ))}
            </Paper>
          </Grid>
        )}

        {/* Response Display */}
        {response && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Response
              </Typography>
              <ReactJson 
                src={response} 
                theme="monokai" 
                collapsed={false}
                displayDataTypes={false}
              />
            </Paper>
          </Grid>
        )}

        {/* Error Display */}
        {error && (
          <Grid item xs={12}>
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          </Grid>
        )}
      </Grid>

      {/* Add Server Dialog */}
      <Dialog 
        open={addDialogOpen} 
        onClose={() => setAddDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Add MCP Server</DialogTitle>
        <DialogContent>
          <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)}>
            <Tab label="Stdio Server" icon={<Terminal />} />
            <Tab label="SSE Server" icon={<Globe />} />
          </Tabs>
          
          {activeTab === 0 && (
            <Box sx={{ pt: 3 }}>
              <TextField
                fullWidth
                label="Server Name"
                value={stdioForm.name}
                onChange={(e) => setStdioForm({ ...stdioForm, name: e.target.value })}
                margin="normal"
                required
              />
              <TextField
                fullWidth
                label="Command"
                value={stdioForm.command}
                onChange={(e) => setStdioForm({ ...stdioForm, command: e.target.value })}
                margin="normal"
                required
                helperText="e.g., npx, node, python"
              />
              <TextField
                fullWidth
                label="Arguments"
                value={stdioForm.args}
                onChange={(e) => setStdioForm({ ...stdioForm, args: e.target.value })}
                margin="normal"
                helperText="Space-separated arguments"
              />
              <FormControl fullWidth margin="normal">
                <InputLabel>Scope</InputLabel>
                <Select
                  value={stdioForm.scope}
                  onChange={(e) => setStdioForm({ ...stdioForm, scope: e.target.value })}
                  label="Scope"
                >
                  <MenuItem value="local">Local (Project-specific)</MenuItem>
                  <MenuItem value="project">Project (Shared via .mcp.json)</MenuItem>
                  <MenuItem value="user">User (All projects)</MenuItem>
                </Select>
              </FormControl>
              <TextField
                fullWidth
                label="Environment Variables (JSON)"
                value={stdioForm.env}
                onChange={(e) => setStdioForm({ ...stdioForm, env: e.target.value })}
                margin="normal"
                multiline
                rows={3}
                helperText='e.g., {"API_KEY": "value"}'
              />
            </Box>
          )}
          
          {activeTab === 1 && (
            <Box sx={{ pt: 3 }}>
              <TextField
                fullWidth
                label="Server Name"
                value={sseForm.name}
                onChange={(e) => setSseForm({ ...sseForm, name: e.target.value })}
                margin="normal"
                required
              />
              <TextField
                fullWidth
                label="URL"
                value={sseForm.url}
                onChange={(e) => setSseForm({ ...sseForm, url: e.target.value })}
                margin="normal"
                required
                helperText="SSE endpoint URL"
              />
              <FormControl fullWidth margin="normal">
                <InputLabel>Scope</InputLabel>
                <Select
                  value={sseForm.scope}
                  onChange={(e) => setSseForm({ ...sseForm, scope: e.target.value })}
                  label="Scope"
                >
                  <MenuItem value="local">Local (Project-specific)</MenuItem>
                  <MenuItem value="project">Project (Shared via .mcp.json)</MenuItem>
                  <MenuItem value="user">User (All projects)</MenuItem>
                </Select>
              </FormControl>
              <TextField
                fullWidth
                label="Environment Variables (JSON)"
                value={sseForm.env}
                onChange={(e) => setSseForm({ ...sseForm, env: e.target.value })}
                margin="normal"
                multiline
                rows={3}
                helperText='e.g., {"API_KEY": "value"}'
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={activeTab === 0 ? handleAddStdioServer : handleAddSseServer} 
            variant="contained"
            disabled={loading === 'mcp_add'}
          >
            {loading === 'mcp_add' ? <CircularProgress size={24} /> : 'Add Server'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add JSON Dialog */}
      <Dialog 
        open={addJsonDialogOpen} 
        onClose={() => setAddJsonDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Add MCP Server from JSON</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label="Server Name"
              value={jsonConfig.name}
              onChange={(e) => setJsonConfig({ ...jsonConfig, name: e.target.value })}
              margin="normal"
              required
            />
            <FormControl fullWidth margin="normal">
              <InputLabel>Scope</InputLabel>
              <Select
                value={jsonConfig.scope}
                onChange={(e) => setJsonConfig({ ...jsonConfig, scope: e.target.value })}
                label="Scope"
              >
                <MenuItem value="local">Local (Project-specific)</MenuItem>
                <MenuItem value="project">Project (Shared via .mcp.json)</MenuItem>
                <MenuItem value="user">User (All projects)</MenuItem>
              </Select>
            </FormControl>
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                JSON Configuration
              </Typography>
              <MonacoEditor
                height="300px"
                language="json"
                theme="vs-dark"
                value={jsonConfig.config}
                onChange={(value) => setJsonConfig({ ...jsonConfig, config: value || '{}' })}
                options={{
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                  fontSize: 12
                }}
              />
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddJsonDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={handleAddJsonServer} 
            variant="contained"
            disabled={loading === 'mcp_add_json' || !jsonConfig.name}
          >
            {loading === 'mcp_add_json' ? <CircularProgress size={24} /> : 'Add Server'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default MCPServerManagement;