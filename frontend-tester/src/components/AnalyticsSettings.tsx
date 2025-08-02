import React, { useState } from 'react';
import { 
  Box, 
  Typography, 
  Button, 
  Grid, 
  Paper, 
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Alert,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow
} from '@mui/material';
import { 
  Analytics as AnalyticsIcon,
  Settings as SettingsIcon,
  Info as InfoIcon,
  TrendingUp as TrendingUpIcon,
  Storage as StorageIcon
} from '@mui/icons-material';
import ReactJson from 'react-json-view';
import MonacoEditor from '@monaco-editor/react';
import MCPClient from '../services/MCPClient';

interface AnalyticsSettingsProps {
  client: MCPClient;
}

const AnalyticsSettings: React.FC<AnalyticsSettingsProps> = ({ client }) => {
  const [loading, setLoading] = useState<string | null>(null);
  const [response, setResponse] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [serverStatus, setServerStatus] = useState<any>(null);
  
  // Dialog states
  const [analyticsDialogOpen, setAnalyticsDialogOpen] = useState(false);
  const [settingsDialogOpen, setSettingsDialogOpen] = useState(false);
  
  // Form states
  const [analyticsQuery, setAnalyticsQuery] = useState({
    metric: 'session_count',
    timeRange: 'last_24h',
    groupBy: 'hour',
    filters: '{}'
  });
  
  const [settingsAction, setSettingsAction] = useState({
    action: 'get',
    key: '',
    value: '{}'
  });

  const handleToolCall = async (toolName: string, params?: any) => {
    setLoading(toolName);
    setError(null);
    try {
      let result;
      switch (toolName) {
        case 'query_analytics':
          const filters = analyticsQuery.filters ? JSON.parse(analyticsQuery.filters) : {};
          result = await client.queryAnalytics({
            metric_type: analyticsQuery.metric,
            time_range: analyticsQuery.timeRange,
            aggregation: analyticsQuery.groupBy,
            filters
          });
          setAnalyticsDialogOpen(false);
          break;
        case 'manage_settings':
          if (settingsAction.action === 'get') {
            result = await client.manageSettings({
              action: 'get',
              key: settingsAction.key || undefined
            });
          } else {
            const value = JSON.parse(settingsAction.value);
            result = await client.manageSettings({
              action: settingsAction.action as 'get' | 'update' | 'reset',
              key: settingsAction.key,
              value
            });
          }
          setSettingsDialogOpen(false);
          break;
        case 'server_status':
          result = await client.serverStatus();
          setServerStatus(result);
          break;
      }
      setResponse(result);
    } catch (err: any) {
      setError(err.message || 'Unknown error occurred');
    } finally {
      setLoading(null);
    }
  };

  const handleQueryAnalytics = () => {
    try {
      handleToolCall('query_analytics');
    } catch (err) {
      setError('Invalid JSON in filters field');
    }
  };

  const handleManageSettings = () => {
    try {
      handleToolCall('manage_settings');
    } catch (err) {
      setError('Invalid JSON in value field');
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Analytics & Settings Tools
      </Typography>
      
      <Grid container spacing={3}>
        {/* Tool Buttons */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Grid container spacing={2}>
              <Grid item>
                <Button
                  variant="contained"
                  startIcon={<AnalyticsIcon />}
                  onClick={() => setAnalyticsDialogOpen(true)}
                  disabled={loading === 'query_analytics'}
                >
                  Query Analytics
                </Button>
              </Grid>
              <Grid item>
                <Button
                  variant="contained"
                  startIcon={<SettingsIcon />}
                  onClick={() => setSettingsDialogOpen(true)}
                  disabled={loading === 'manage_settings'}
                >
                  Manage Settings
                </Button>
              </Grid>
              <Grid item>
                <Button
                  variant="contained"
                  startIcon={<InfoIcon />}
                  onClick={() => handleToolCall('server_status')}
                  disabled={loading === 'server_status'}
                >
                  {loading === 'server_status' ? <CircularProgress size={24} /> : 'Server Status'}
                </Button>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Server Status Display */}
        {serverStatus && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Server Status
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Version
                    </Typography>
                    <Typography variant="h6">
                      {serverStatus.version}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Uptime
                    </Typography>
                    <Typography variant="h6">
                      {Math.floor(serverStatus.uptime / 3600)}h {Math.floor((serverStatus.uptime % 3600) / 60)}m
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Active Sessions
                    </Typography>
                    <Typography variant="h6">
                      {serverStatus.activeSessions}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Total Requests
                    </Typography>
                    <Typography variant="h6">
                      {serverStatus.totalRequests?.toLocaleString()}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Memory Usage
                    </Typography>
                    <Typography variant="h6">
                      {formatBytes(serverStatus.memoryUsage?.heapUsed || 0)}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      CPU Usage
                    </Typography>
                    <Typography variant="h6">
                      {serverStatus.cpuUsage?.toFixed(1)}%
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
              
              {serverStatus.features && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Enabled Features
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {Object.entries(serverStatus.features).map(([feature, enabled]) => (
                      <Chip
                        key={feature}
                        label={feature}
                        color={enabled ? 'success' : 'default'}
                        size="small"
                      />
                    ))}
                  </Box>
                </Box>
              )}
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

      {/* Query Analytics Dialog */}
      <Dialog 
        open={analyticsDialogOpen} 
        onClose={() => setAnalyticsDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Query Analytics</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <FormControl fullWidth margin="normal">
              <InputLabel>Metric</InputLabel>
              <Select
                value={analyticsQuery.metric}
                onChange={(e) => setAnalyticsQuery({ ...analyticsQuery, metric: e.target.value })}
                label="Metric"
              >
                <MenuItem value="session_count">Session Count</MenuItem>
                <MenuItem value="message_count">Message Count</MenuItem>
                <MenuItem value="agent_usage">Agent Usage</MenuItem>
                <MenuItem value="tool_usage">Tool Usage</MenuItem>
                <MenuItem value="error_rate">Error Rate</MenuItem>
                <MenuItem value="response_time">Response Time</MenuItem>
              </Select>
            </FormControl>
            
            <FormControl fullWidth margin="normal">
              <InputLabel>Time Range</InputLabel>
              <Select
                value={analyticsQuery.timeRange}
                onChange={(e) => setAnalyticsQuery({ ...analyticsQuery, timeRange: e.target.value })}
                label="Time Range"
              >
                <MenuItem value="last_hour">Last Hour</MenuItem>
                <MenuItem value="last_24h">Last 24 Hours</MenuItem>
                <MenuItem value="last_7d">Last 7 Days</MenuItem>
                <MenuItem value="last_30d">Last 30 Days</MenuItem>
                <MenuItem value="custom">Custom Range</MenuItem>
              </Select>
            </FormControl>
            
            <FormControl fullWidth margin="normal">
              <InputLabel>Group By</InputLabel>
              <Select
                value={analyticsQuery.groupBy}
                onChange={(e) => setAnalyticsQuery({ ...analyticsQuery, groupBy: e.target.value })}
                label="Group By"
              >
                <MenuItem value="minute">Minute</MenuItem>
                <MenuItem value="hour">Hour</MenuItem>
                <MenuItem value="day">Day</MenuItem>
                <MenuItem value="week">Week</MenuItem>
                <MenuItem value="agent">Agent</MenuItem>
                <MenuItem value="session">Session</MenuItem>
              </Select>
            </FormControl>
            
            <TextField
              fullWidth
              label="Filters (JSON)"
              value={analyticsQuery.filters}
              onChange={(e) => setAnalyticsQuery({ ...analyticsQuery, filters: e.target.value })}
              margin="normal"
              multiline
              rows={3}
              helperText='e.g., {"agentId": "agent-123", "sessionId": "session-456"}'
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAnalyticsDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={handleQueryAnalytics} 
            variant="contained"
            disabled={loading === 'query_analytics'}
          >
            {loading === 'query_analytics' ? <CircularProgress size={24} /> : 'Query'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Manage Settings Dialog */}
      <Dialog 
        open={settingsDialogOpen} 
        onClose={() => setSettingsDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Manage Settings</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <FormControl fullWidth margin="normal">
              <InputLabel>Action</InputLabel>
              <Select
                value={settingsAction.action}
                onChange={(e) => setSettingsAction({ ...settingsAction, action: e.target.value })}
                label="Action"
              >
                <MenuItem value="get">Get Settings</MenuItem>
                <MenuItem value="update">Update Setting</MenuItem>
                <MenuItem value="reset">Reset Setting</MenuItem>
              </Select>
            </FormControl>
            
            <TextField
              fullWidth
              label="Key (optional for 'get all')"
              value={settingsAction.key}
              onChange={(e) => setSettingsAction({ ...settingsAction, key: e.target.value })}
              margin="normal"
              helperText="Setting key, e.g., 'analytics.enabled' or leave empty to get all"
            />
            
            {settingsAction.action === 'update' && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Value (JSON)
                </Typography>
                <MonacoEditor
                  height="200px"
                  language="json"
                  theme="vs-dark"
                  value={settingsAction.value}
                  onChange={(value) => setSettingsAction({ ...settingsAction, value: value || '{}' })}
                  options={{
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                    fontSize: 12
                  }}
                />
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSettingsDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={handleManageSettings} 
            variant="contained"
            disabled={loading === 'manage_settings'}
          >
            {loading === 'manage_settings' ? <CircularProgress size={24} /> : 'Execute'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AnalyticsSettings;