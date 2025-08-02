import React, { useState } from 'react';
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
  Chip
} from '@mui/material';
import { 
  Save as SaveIcon,
  List as ListIcon,
  Restore as RestoreIcon,
  AccountTree as BranchIcon,
  ContentCopy as CopyIcon,
  History as HistoryIcon
} from '@mui/icons-material';
import ReactJson from 'react-json-view';
import MCPClient from '../services/MCPClient';

interface CheckpointManagementProps {
  client: MCPClient;
}

const CheckpointManagement: React.FC<CheckpointManagementProps> = ({ client }) => {
  const [loading, setLoading] = useState<string | null>(null);
  const [response, setResponse] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkpoints, setCheckpoints] = useState<any[]>([]);
  
  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [branchDialogOpen, setBranchDialogOpen] = useState(false);
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<any>(null);
  
  // Form states
  const [createParams, setCreateParams] = useState({
    sessionId: '',
    message: '',
    includeAgents: true,
    metadata: '{}'
  });
  
  const [branchParams, setBranchParams] = useState({
    name: '',
    description: ''
  });

  const handleToolCall = async (toolName: string, params?: any) => {
    setLoading(toolName);
    setError(null);
    try {
      let result;
      switch (toolName) {
        case 'create_checkpoint':
          result = await client.createCheckpoint(params);
          setCreateDialogOpen(false);
          handleListCheckpoints();
          break;
        case 'list_checkpoints':
          result = await client.listCheckpoints();
          setCheckpoints(result.checkpoints || []);
          break;
        case 'restore_checkpoint':
          result = await client.restoreCheckpoint(params);
          handleListCheckpoints();
          break;
        case 'branch_checkpoint':
          result = await client.branchCheckpoint(params);
          setBranchDialogOpen(false);
          handleListCheckpoints();
          break;
      }
      setResponse(result);
    } catch (err: any) {
      setError(err.message || 'Unknown error occurred');
    } finally {
      setLoading(null);
    }
  };

  const handleListCheckpoints = () => {
    handleToolCall('list_checkpoints');
  };

  const handleCreateCheckpoint = () => {
    try {
      const metadata = JSON.parse(createParams.metadata);
      handleToolCall('create_checkpoint', {
        sessionId: createParams.sessionId,
        message: createParams.message,
        includeAgents: createParams.includeAgents,
        metadata
      });
    } catch (err) {
      setError('Invalid JSON in metadata field');
    }
  };

  const handleBranchCheckpoint = () => {
    if (selectedCheckpoint) {
      handleToolCall('branch_checkpoint', {
        checkpointId: selectedCheckpoint.id,
        name: branchParams.name,
        description: branchParams.description
      });
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Checkpoint Management Tools
      </Typography>
      
      <Grid container spacing={3}>
        {/* Tool Buttons */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Grid container spacing={2}>
              <Grid item>
                <Button
                  variant="contained"
                  startIcon={<SaveIcon />}
                  onClick={() => setCreateDialogOpen(true)}
                  disabled={loading === 'create_checkpoint'}
                >
                  Create Checkpoint
                </Button>
              </Grid>
              <Grid item>
                <Button
                  variant="contained"
                  startIcon={<ListIcon />}
                  onClick={handleListCheckpoints}
                  disabled={loading === 'list_checkpoints'}
                >
                  {loading === 'list_checkpoints' ? <CircularProgress size={24} /> : 'List Checkpoints'}
                </Button>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Checkpoints List */}
        {checkpoints.length > 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Available Checkpoints
              </Typography>
              <List>
                {checkpoints.map((checkpoint) => (
                  <ListItem key={checkpoint.id} divider>
                    <ListItemText
                      primary={checkpoint.message || `Checkpoint ${checkpoint.id}`}
                      secondary={
                        <Box>
                          <Typography variant="caption" display="block">
                            ID: {checkpoint.id}
                          </Typography>
                          <Typography variant="caption" display="block">
                            Created: {new Date(checkpoint.created_at).toLocaleString()}
                          </Typography>
                          {checkpoint.sessionId && (
                            <Typography variant="caption" display="block">
                              Session: {checkpoint.sessionId}
                            </Typography>
                          )}
                          {checkpoint.branch && (
                            <Chip 
                              label={`Branch: ${checkpoint.branch}`} 
                              size="small" 
                              color="primary" 
                              sx={{ mt: 0.5 }}
                            />
                          )}
                        </Box>
                      }
                    />
                    <ListItemSecondaryAction>
                      <IconButton
                        onClick={() => {
                          if (window.confirm('Restore this checkpoint? This will reset the current state.')) {
                            handleToolCall('restore_checkpoint', { checkpointId: checkpoint.id });
                          }
                        }}
                        disabled={loading === 'restore_checkpoint'}
                        title="Restore Checkpoint"
                      >
                        <RestoreIcon />
                      </IconButton>
                      <IconButton
                        onClick={() => {
                          setSelectedCheckpoint(checkpoint);
                          setBranchDialogOpen(true);
                        }}
                        title="Branch from Checkpoint"
                      >
                        <BranchIcon />
                      </IconButton>
                    </ListItemSecondaryAction>
                  </ListItem>
                ))}
              </List>
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

      {/* Create Checkpoint Dialog */}
      <Dialog 
        open={createDialogOpen} 
        onClose={() => setCreateDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create Checkpoint</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label="Session ID"
              value={createParams.sessionId}
              onChange={(e) => setCreateParams({ ...createParams, sessionId: e.target.value })}
              margin="normal"
              helperText="ID of the session to checkpoint"
            />
            <TextField
              fullWidth
              label="Message"
              value={createParams.message}
              onChange={(e) => setCreateParams({ ...createParams, message: e.target.value })}
              margin="normal"
              multiline
              rows={2}
              helperText="Description of this checkpoint"
            />
            <TextField
              fullWidth
              label="Metadata (JSON)"
              value={createParams.metadata}
              onChange={(e) => setCreateParams({ ...createParams, metadata: e.target.value })}
              margin="normal"
              multiline
              rows={3}
              helperText="Additional metadata as JSON object"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={handleCreateCheckpoint} 
            variant="contained"
            disabled={loading === 'create_checkpoint'}
          >
            {loading === 'create_checkpoint' ? <CircularProgress size={24} /> : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Branch Checkpoint Dialog */}
      <Dialog 
        open={branchDialogOpen} 
        onClose={() => setBranchDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Branch from Checkpoint</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            {selectedCheckpoint && (
              <Alert severity="info" sx={{ mb: 2 }}>
                Branching from: {selectedCheckpoint.message || `Checkpoint ${selectedCheckpoint.id}`}
              </Alert>
            )}
            <TextField
              fullWidth
              label="Branch Name"
              value={branchParams.name}
              onChange={(e) => setBranchParams({ ...branchParams, name: e.target.value })}
              margin="normal"
              helperText="Name for the new branch"
            />
            <TextField
              fullWidth
              label="Description"
              value={branchParams.description}
              onChange={(e) => setBranchParams({ ...branchParams, description: e.target.value })}
              margin="normal"
              multiline
              rows={2}
              helperText="Description of the branch"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBranchDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={handleBranchCheckpoint} 
            variant="contained"
            disabled={loading === 'branch_checkpoint' || !branchParams.name}
          >
            {loading === 'branch_checkpoint' ? <CircularProgress size={24} /> : 'Create Branch'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default CheckpointManagement;