import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Grid,
  Alert,
  CircularProgress,
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
  Chip,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Divider,
  FormGroup,
  FormControlLabel,
  Checkbox
} from '@mui/material';
import {
  Add,
  PlayArrow,
  Assignment,
  Refresh,
  SmartToy,
  Task
} from '@mui/icons-material';
import ReactJson from 'react-json-view';
import Editor from '@monaco-editor/react';
import MCPClient from '../services/MCPClient';

interface AgentManagementProps {
  client: MCPClient;
}

interface Agent {
  id: string;
  name: string;
  type: string;
  status: string;
  capabilities: string[];
  created_at: string;
}

const AgentManagement: React.FC<AgentManagementProps> = ({ client }) => {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  
  // Create agent dialog
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [agentName, setAgentName] = useState('test-agent');
  const [agentType, setAgentType] = useState('code-assistant');
  const [capabilities, setCapabilities] = useState({
    'code-completion': true,
    'code-review': true,
    'documentation': false,
    'testing': false,
    'debugging': false
  });
  const [agentConfig, setAgentConfig] = useState('{\n  "model": "gpt-4",\n  "temperature": 0.7\n}');
  
  // Execute agent dialog
  const [executeDialogOpen, setExecuteDialogOpen] = useState(false);
  const [action, setAction] = useState('analyze');
  const [parameters, setParameters] = useState('{\n  "code": "print(\\"Hello World\\")",\n  "language": "python"\n}');
  
  // Assign task dialog
  const [taskDialogOpen, setTaskDialogOpen] = useState(false);
  const [taskDescription, setTaskDescription] = useState('Review the latest pull request');
  const [taskPriority, setTaskPriority] = useState('medium');
  const [taskContext, setTaskContext] = useState('{\n  "pr_number": 123,\n  "repository": "shannon-mcp"\n}');
  
  // Response display
  const [lastResponse, setLastResponse] = useState<any>(null);

  useEffect(() => {
    // Load agents on mount
    handleListAgents();
  }, []);

  const handleCreateAgent = async () => {
    setLoading('create');
    setError(null);
    try {
      const selectedCapabilities = Object.entries(capabilities)
        .filter(([_, enabled]) => enabled)
        .map(([cap]) => cap);
      
      const params = {
        name: agentName,
        type: agentType,
        capabilities: selectedCapabilities,
        config: JSON.parse(agentConfig)
      };
      
      const result = await client.createAgent(params);
      setLastResponse(result);
      setCreateDialogOpen(false);
      
      // Refresh agents list
      await handleListAgents();
    } catch (err: any) {
      setError(`Create agent failed: ${err.message}`);
    } finally {
      setLoading(null);
    }
  };

  const handleListAgents = async () => {
    setLoading('list');
    setError(null);
    try {
      const result = await client.listAgents({ status: 'all' });
      setAgents(result.agents || []);
      setLastResponse(result);
    } catch (err: any) {
      setError(`List agents failed: ${err.message}`);
    } finally {
      setLoading(null);
    }
  };

  const handleExecuteAgent = async () => {
    if (!selectedAgent) return;
    
    setLoading('execute');
    setError(null);
    try {
      const result = await client.executeAgent({
        agent_id: selectedAgent.id,
        action: action,
        parameters: JSON.parse(parameters)
      });
      setLastResponse(result);
      setExecuteDialogOpen(false);
    } catch (err: any) {
      setError(`Execute agent failed: ${err.message}`);
    } finally {
      setLoading(null);
    }
  };

  const handleAssignTask = async () => {
    if (!selectedAgent) return;
    
    setLoading('assign');
    setError(null);
    try {
      const result = await client.assignTask({
        agent_id: selectedAgent.id,
        task: taskDescription,
        priority: taskPriority,
        context: JSON.parse(taskContext)
      });
      setLastResponse(result);
      setTaskDialogOpen(false);
    } catch (err: any) {
      setError(`Assign task failed: ${err.message}`);
    } finally {
      setLoading(null);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'success';
      case 'idle': return 'info';
      case 'busy': return 'warning';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const agentTypes = [
    'code-assistant',
    'test-runner',
    'documentation-writer',
    'security-scanner',
    'performance-analyzer',
    'refactoring-assistant'
  ];

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Agent Management Tools (4 tools)
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        Create and manage AI agents for various development tasks
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Tool 7: Create Agent */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <SmartToy sx={{ mr: 1 }} />
                <Typography variant="h6">create_agent</Typography>
                <Chip label="Tool #7" size="small" sx={{ ml: 'auto' }} />
              </Box>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                Creates a new AI agent with specified capabilities
              </Typography>

              <Button
                variant="contained"
                fullWidth
                onClick={() => setCreateDialogOpen(true)}
                startIcon={<Add />}
              >
                Create New Agent
              </Button>
            </CardContent>
          </Card>
        </Grid>

        {/* Tool 8: List Agents */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <SmartToy sx={{ mr: 1 }} />
                <Typography variant="h6">list_agents</Typography>
                <Chip label="Tool #8" size="small" sx={{ ml: 'auto' }} />
              </Box>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                Lists all available agents and their status
              </Typography>

              <Button
                variant="contained"
                fullWidth
                onClick={handleListAgents}
                disabled={loading === 'list'}
                startIcon={loading === 'list' ? <CircularProgress size={20} /> : <Refresh />}
              >
                Refresh Agents
              </Button>
            </CardContent>
          </Card>
        </Grid>

        {/* Agents List */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Available Agents ({agents.length})
              </Typography>
              
              {agents.length === 0 ? (
                <Alert severity="info">No agents found. Create a new agent to get started.</Alert>
              ) : (
                <List>
                  {agents.map((agent) => (
                    <ListItem
                      key={agent.id}
                      sx={{
                        border: 1,
                        borderColor: 'divider',
                        borderRadius: 1,
                        mb: 1
                      }}
                    >
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="subtitle1">
                              {agent.name}
                            </Typography>
                            <Chip
                              label={agent.type}
                              size="small"
                              variant="outlined"
                            />
                            <Chip
                              label={agent.status}
                              size="small"
                              color={getStatusColor(agent.status) as any}
                            />
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2">
                              ID: {agent.id}
                            </Typography>
                            <Typography variant="body2">
                              Capabilities: {agent.capabilities.join(', ')}
                            </Typography>
                            <Typography variant="caption">
                              Created: {new Date(agent.created_at).toLocaleString()}
                            </Typography>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          {/* Tool 9: Execute Agent */}
                          <IconButton
                            color="primary"
                            onClick={() => {
                              setSelectedAgent(agent);
                              setExecuteDialogOpen(true);
                            }}
                            disabled={agent.status === 'busy'}
                            title="Execute agent (Tool #9)"
                          >
                            <PlayArrow />
                          </IconButton>
                          
                          {/* Tool 10: Assign Task */}
                          <IconButton
                            color="secondary"
                            onClick={() => {
                              setSelectedAgent(agent);
                              setTaskDialogOpen(true);
                            }}
                            disabled={agent.status === 'busy'}
                            title="Assign task (Tool #10)"
                          >
                            <Assignment />
                          </IconButton>
                        </Box>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Last Response */}
        {lastResponse && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Last Response
                </Typography>
                <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                  <ReactJson
                    src={lastResponse}
                    theme="monokai"
                    displayDataTypes={false}
                    style={{ fontSize: '12px' }}
                  />
                </Paper>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>

      {/* Create Agent Dialog */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Create New Agent</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Agent Name"
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              fullWidth
              required
            />
            <FormControl fullWidth>
              <InputLabel>Agent Type</InputLabel>
              <Select
                value={agentType}
                onChange={(e) => setAgentType(e.target.value)}
                label="Agent Type"
              >
                {agentTypes.map((type) => (
                  <MenuItem key={type} value={type}>{type}</MenuItem>
                ))}
              </Select>
            </FormControl>
            
            <Typography variant="subtitle2">Capabilities</Typography>
            <FormGroup row>
              {Object.entries(capabilities).map(([cap, enabled]) => (
                <FormControlLabel
                  key={cap}
                  control={
                    <Checkbox
                      checked={enabled}
                      onChange={(e) => setCapabilities({...capabilities, [cap]: e.target.checked})}
                    />
                  }
                  label={cap}
                />
              ))}
            </FormGroup>
            
            <Typography variant="subtitle2">Configuration (JSON)</Typography>
            <Paper variant="outlined">
              <Editor
                height="150px"
                defaultLanguage="json"
                value={agentConfig}
                onChange={(value) => setAgentConfig(value || '')}
                theme="vs-dark"
                options={{
                  minimap: { enabled: false },
                  fontSize: 12
                }}
              />
            </Paper>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleCreateAgent}
            variant="contained"
            disabled={loading === 'create' || !agentName}
          >
            {loading === 'create' ? <CircularProgress size={20} /> : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Execute Agent Dialog */}
      <Dialog open={executeDialogOpen} onClose={() => setExecuteDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Execute Agent: {selectedAgent?.name}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <FormControl fullWidth>
              <InputLabel>Action</InputLabel>
              <Select
                value={action}
                onChange={(e) => setAction(e.target.value)}
                label="Action"
              >
                <MenuItem value="analyze">Analyze Code</MenuItem>
                <MenuItem value="refactor">Refactor Code</MenuItem>
                <MenuItem value="test">Generate Tests</MenuItem>
                <MenuItem value="document">Generate Documentation</MenuItem>
                <MenuItem value="review">Code Review</MenuItem>
              </Select>
            </FormControl>
            
            <Typography variant="subtitle2">Parameters (JSON)</Typography>
            <Paper variant="outlined">
              <Editor
                height="200px"
                defaultLanguage="json"
                value={parameters}
                onChange={(value) => setParameters(value || '')}
                theme="vs-dark"
                options={{
                  minimap: { enabled: false },
                  fontSize: 12
                }}
              />
            </Paper>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setExecuteDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleExecuteAgent}
            variant="contained"
            disabled={loading === 'execute'}
            startIcon={<PlayArrow />}
          >
            {loading === 'execute' ? <CircularProgress size={20} /> : 'Execute'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Assign Task Dialog */}
      <Dialog open={taskDialogOpen} onClose={() => setTaskDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Assign Task to: {selectedAgent?.name}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Task Description"
              value={taskDescription}
              onChange={(e) => setTaskDescription(e.target.value)}
              fullWidth
              multiline
              rows={2}
              required
            />
            <FormControl fullWidth>
              <InputLabel>Priority</InputLabel>
              <Select
                value={taskPriority}
                onChange={(e) => setTaskPriority(e.target.value)}
                label="Priority"
              >
                <MenuItem value="low">Low</MenuItem>
                <MenuItem value="medium">Medium</MenuItem>
                <MenuItem value="high">High</MenuItem>
                <MenuItem value="critical">Critical</MenuItem>
              </Select>
            </FormControl>
            
            <Typography variant="subtitle2">Task Context (JSON)</Typography>
            <Paper variant="outlined">
              <Editor
                height="150px"
                defaultLanguage="json"
                value={taskContext}
                onChange={(value) => setTaskContext(value || '')}
                theme="vs-dark"
                options={{
                  minimap: { enabled: false },
                  fontSize: 12
                }}
              />
            </Paper>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTaskDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleAssignTask}
            variant="contained"
            disabled={loading === 'assign' || !taskDescription}
            startIcon={<Assignment />}
          >
            {loading === 'assign' ? <CircularProgress size={20} /> : 'Assign'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AgentManagement;