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
  Divider
} from '@mui/material';
import {
  Add,
  Cancel,
  Send,
  Refresh,
  Terminal,
  PlayArrow,
  Stop
} from '@mui/icons-material';
import ReactJson from 'react-json-view';
import MCPClient from '../services/MCPClient';

interface SessionManagementProps {
  client: MCPClient;
}

interface Session {
  id: string;
  project_id: string;
  command: string;
  state: string;
  created_at: string;
  pid?: number;
}

const SessionManagement: React.FC<SessionManagementProps> = ({ client }) => {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  
  // Create session dialog
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [projectId, setProjectId] = useState('test-project');
  const [command, setCommand] = useState('echo "Hello from Shannon MCP"');
  const [args, setArgs] = useState('');
  const [env, setEnv] = useState('');
  
  // Send message dialog
  const [messageDialogOpen, setMessageDialogOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('stdin');

  // Response display
  const [lastResponse, setLastResponse] = useState<any>(null);

  useEffect(() => {
    // Load sessions on mount
    handleListSessions();
  }, []);

  const handleCreateSession = async () => {
    setLoading('create');
    setError(null);
    try {
      const params = {
        project_id: projectId,
        command: command,
        args: args ? args.split(' ') : undefined,
        env: env ? JSON.parse(env) : undefined
      };
      
      const result = await client.createSession(params);
      setLastResponse(result);
      setCreateDialogOpen(false);
      
      // Refresh sessions list
      await handleListSessions();
    } catch (err: any) {
      setError(`Create session failed: ${err.message}`);
    } finally {
      setLoading(null);
    }
  };

  const handleListSessions = async () => {
    setLoading('list');
    setError(null);
    try {
      const result = await client.listSessions({ status: 'all' });
      setSessions(result.sessions || []);
      setLastResponse(result);
    } catch (err: any) {
      setError(`List sessions failed: ${err.message}`);
    } finally {
      setLoading(null);
    }
  };

  const handleCancelSession = async (sessionId: string) => {
    setLoading(`cancel-${sessionId}`);
    setError(null);
    try {
      const result = await client.cancelSession({
        session_id: sessionId,
        reason: 'User requested cancellation'
      });
      setLastResponse(result);
      
      // Refresh sessions list
      await handleListSessions();
    } catch (err: any) {
      setError(`Cancel session failed: ${err.message}`);
    } finally {
      setLoading(null);
    }
  };

  const handleSendMessage = async () => {
    if (!selectedSession) return;
    
    setLoading('send');
    setError(null);
    try {
      const result = await client.sendMessage({
        session_id: selectedSession.id,
        message: message,
        message_type: messageType
      });
      setLastResponse(result);
      setMessageDialogOpen(false);
      setMessage('');
    } catch (err: any) {
      setError(`Send message failed: ${err.message}`);
    } finally {
      setLoading(null);
    }
  };

  const getStateColor = (state: string) => {
    switch (state) {
      case 'running': return 'success';
      case 'created': return 'info';
      case 'cancelled': return 'warning';
      case 'failed': return 'error';
      default: return 'default';
    }
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Session Management Tools (4 tools)
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        Create, manage, and interact with Claude Code sessions
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Tool 3: Create Session */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Add sx={{ mr: 1 }} />
                <Typography variant="h6">create_session</Typography>
                <Chip label="Tool #3" size="small" sx={{ ml: 'auto' }} />
              </Box>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                Creates a new Claude Code session with specified parameters
              </Typography>

              <Button
                variant="contained"
                fullWidth
                onClick={() => setCreateDialogOpen(true)}
                startIcon={<Add />}
              >
                Create New Session
              </Button>
            </CardContent>
          </Card>
        </Grid>

        {/* Tool 4: List Sessions */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Terminal sx={{ mr: 1 }} />
                <Typography variant="h6">list_sessions</Typography>
                <Chip label="Tool #4" size="small" sx={{ ml: 'auto' }} />
              </Box>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                Lists all active and inactive sessions
              </Typography>

              <Button
                variant="contained"
                fullWidth
                onClick={handleListSessions}
                disabled={loading === 'list'}
                startIcon={loading === 'list' ? <CircularProgress size={20} /> : <Refresh />}
              >
                Refresh Sessions
              </Button>
            </CardContent>
          </Card>
        </Grid>

        {/* Sessions List */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Active Sessions ({sessions.length})
              </Typography>
              
              {sessions.length === 0 ? (
                <Alert severity="info">No sessions found. Create a new session to get started.</Alert>
              ) : (
                <List>
                  {sessions.map((session) => (
                    <ListItem
                      key={session.id}
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
                              Session: {session.id}
                            </Typography>
                            <Chip
                              label={session.state}
                              size="small"
                              color={getStateColor(session.state) as any}
                            />
                            {session.pid && (
                              <Chip
                                label={`PID: ${session.pid}`}
                                size="small"
                                variant="outlined"
                              />
                            )}
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2">
                              Command: <code>{session.command}</code>
                            </Typography>
                            <Typography variant="body2">
                              Project: {session.project_id}
                            </Typography>
                            <Typography variant="caption">
                              Created: {new Date(session.created_at).toLocaleString()}
                            </Typography>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          {/* Tool 5: Cancel Session */}
                          <IconButton
                            color="error"
                            onClick={() => handleCancelSession(session.id)}
                            disabled={loading === `cancel-${session.id}` || session.state !== 'running'}
                            title="Cancel session (Tool #5)"
                          >
                            {loading === `cancel-${session.id}` ? (
                              <CircularProgress size={20} />
                            ) : (
                              <Stop />
                            )}
                          </IconButton>
                          
                          {/* Tool 6: Send Message */}
                          <IconButton
                            color="primary"
                            onClick={() => {
                              setSelectedSession(session);
                              setMessageDialogOpen(true);
                            }}
                            disabled={session.state !== 'running'}
                            title="Send message (Tool #6)"
                          >
                            <Send />
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

      {/* Create Session Dialog */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Session</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Project ID"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              fullWidth
              required
            />
            <TextField
              label="Command"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              fullWidth
              required
              helperText="The command to execute in the session"
            />
            <TextField
              label="Arguments"
              value={args}
              onChange={(e) => setArgs(e.target.value)}
              fullWidth
              helperText="Space-separated arguments (optional)"
            />
            <TextField
              label="Environment Variables"
              value={env}
              onChange={(e) => setEnv(e.target.value)}
              fullWidth
              multiline
              rows={2}
              helperText='JSON format, e.g., {"KEY": "value"} (optional)'
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleCreateSession}
            variant="contained"
            disabled={loading === 'create' || !projectId || !command}
          >
            {loading === 'create' ? <CircularProgress size={20} /> : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Send Message Dialog */}
      <Dialog open={messageDialogOpen} onClose={() => setMessageDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Send Message to Session</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <Typography variant="body2">
              Session: {selectedSession?.id}
            </Typography>
            <TextField
              label="Message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              fullWidth
              multiline
              rows={3}
              required
            />
            <FormControl fullWidth>
              <InputLabel>Message Type</InputLabel>
              <Select
                value={messageType}
                onChange={(e) => setMessageType(e.target.value)}
                label="Message Type"
              >
                <MenuItem value="stdin">stdin</MenuItem>
                <MenuItem value="signal">signal</MenuItem>
                <MenuItem value="control">control</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setMessageDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleSendMessage}
            variant="contained"
            disabled={loading === 'send' || !message}
            startIcon={<Send />}
          >
            {loading === 'send' ? <CircularProgress size={20} /> : 'Send'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SessionManagement;