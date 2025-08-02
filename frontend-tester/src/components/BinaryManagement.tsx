import React, { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Grid,
  Alert,
  CircularProgress,
  Divider,
  Chip,
  List,
  ListItem,
  ListItemText,
  Paper
} from '@mui/material';
import { Search, Update } from '@mui/icons-material';
import ReactJson from 'react-json-view';
import MCPClient from '../services/MCPClient';

interface BinaryManagementProps {
  client: MCPClient;
}

const BinaryManagement: React.FC<BinaryManagementProps> = ({ client }) => {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [binaryInfo, setBinaryInfo] = useState<any>(null);
  const [updateInfo, setUpdateInfo] = useState<any>(null);

  const handleFindBinary = async () => {
    setLoading('find');
    setError(null);
    setBinaryInfo(null);
    try {
      const result = await client.findClaudeBinary();
      setBinaryInfo(result);
    } catch (err: any) {
      setError(`Find binary failed: ${err.message}`);
    } finally {
      setLoading(null);
    }
  };

  const handleCheckUpdates = async () => {
    setLoading('update');
    setError(null);
    setUpdateInfo(null);
    try {
      const result = await client.checkClaudeUpdates();
      setUpdateInfo(result);
    } catch (err: any) {
      setError(`Check updates failed: ${err.message}`);
    } finally {
      setLoading(null);
    }
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Binary Management Tools (2 tools)
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        Manage Claude Code binary discovery and updates
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Tool 1: Find Claude Binary */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Search sx={{ mr: 1 }} />
                <Typography variant="h6">find_claude_binary</Typography>
                <Chip label="Tool #1" size="small" sx={{ ml: 'auto' }} />
              </Box>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                Discovers Claude Code binary installation on the system
              </Typography>

              <Button
                variant="contained"
                fullWidth
                onClick={handleFindBinary}
                disabled={loading === 'find'}
                startIcon={loading === 'find' ? <CircularProgress size={20} /> : <Search />}
              >
                Find Claude Binary
              </Button>

              {binaryInfo && (
                <Box sx={{ mt: 2 }}>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" gutterBottom>
                    Binary Information:
                  </Typography>
                  
                  {binaryInfo.binary_info ? (
                    <List dense>
                      <ListItem>
                        <ListItemText
                          primary="Path"
                          secondary={binaryInfo.binary_info.path || 'Not found'}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText
                          primary="Version"
                          secondary={binaryInfo.binary_info.version || 'Unknown'}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText
                          primary="Executable"
                          secondary={binaryInfo.binary_info.is_executable ? 'Yes' : 'No'}
                        />
                      </ListItem>
                    </List>
                  ) : (
                    <Alert severity="warning">No binary found</Alert>
                  )}

                  <Paper sx={{ p: 1, mt: 2, bgcolor: 'background.default' }}>
                    <Typography variant="caption" display="block" gutterBottom>
                      Raw Response:
                    </Typography>
                    <ReactJson
                      src={binaryInfo}
                      theme="monokai"
                      collapsed={1}
                      displayDataTypes={false}
                      style={{ fontSize: '12px' }}
                    />
                  </Paper>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Tool 2: Check Claude Updates */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Update sx={{ mr: 1 }} />
                <Typography variant="h6">check_claude_updates</Typography>
                <Chip label="Tool #2" size="small" sx={{ ml: 'auto' }} />
              </Box>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                Checks for available Claude Code updates
              </Typography>

              <Button
                variant="contained"
                fullWidth
                onClick={handleCheckUpdates}
                disabled={loading === 'update'}
                startIcon={loading === 'update' ? <CircularProgress size={20} /> : <Update />}
              >
                Check for Updates
              </Button>

              {updateInfo && (
                <Box sx={{ mt: 2 }}>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" gutterBottom>
                    Update Status:
                  </Typography>
                  
                  <List dense>
                    <ListItem>
                      <ListItemText
                        primary="Update Available"
                        secondary={
                          <Chip
                            label={updateInfo.update_available ? 'Yes' : 'No'}
                            color={updateInfo.update_available ? 'warning' : 'success'}
                            size="small"
                          />
                        }
                      />
                    </ListItem>
                    {updateInfo.current_version && (
                      <ListItem>
                        <ListItemText
                          primary="Current Version"
                          secondary={updateInfo.current_version}
                        />
                      </ListItem>
                    )}
                    {updateInfo.latest_version && (
                      <ListItem>
                        <ListItemText
                          primary="Latest Version"
                          secondary={updateInfo.latest_version}
                        />
                      </ListItem>
                    )}
                  </List>

                  <Paper sx={{ p: 1, mt: 2, bgcolor: 'background.default' }}>
                    <Typography variant="caption" display="block" gutterBottom>
                      Raw Response:
                    </Typography>
                    <ReactJson
                      src={updateInfo}
                      theme="monokai"
                      collapsed={1}
                      displayDataTypes={false}
                      style={{ fontSize: '12px' }}
                    />
                  </Paper>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default BinaryManagement;