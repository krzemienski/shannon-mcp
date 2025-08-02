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
  CardActions,
  Divider,
  FormControlLabel,
  Switch,
  Tooltip
} from '@mui/material';
import { 
  CreateNewFolder,
  List as ListIcon,
  Info,
  Edit,
  FileCopy,
  Archive,
  Folder,
  PlayArrow,
  Save,
  CheckCircle,
  Error as ErrorIcon,
  Refresh,
  FolderOpen
} from '@mui/icons-material';
import ReactJson from 'react-json-view';
import MCPClient from '../services/MCPClient';

interface ProjectManagementProps {
  client: MCPClient;
}

const ProjectManagement: React.FC<ProjectManagementProps> = ({ client }) => {
  const [loading, setLoading] = useState<string | null>(null);
  const [response, setResponse] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProject, setSelectedProject] = useState<any>(null);
  const [projectSessions, setProjectSessions] = useState<any[]>([]);
  
  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [updateDialogOpen, setUpdateDialogOpen] = useState(false);
  const [cloneDialogOpen, setCloneDialogOpen] = useState(false);
  
  // Form states
  const [createParams, setCreateParams] = useState({
    name: '',
    path: '',
    description: '',
    metadata: '{}'
  });
  
  const [updateParams, setUpdateParams] = useState({
    name: '',
    description: '',
    metadata: '{}'
  });
  
  const [cloneParams, setCloneParams] = useState({
    sourcePath: '',
    targetPath: '',
    includeHistory: true
  });

  useEffect(() => {
    handleListProjects();
  }, []);

  const handleToolCall = async (toolName: string, params?: any) => {
    setLoading(toolName);
    setError(null);
    try {
      let result;
      switch (toolName) {
        case 'create_project':
          result = await client.createProject(params);
          setCreateDialogOpen(false);
          handleListProjects();
          break;
        case 'list_projects':
          result = await client.listProjects();
          setProjects(result.projects || result || []);
          break;
        case 'get_project':
          result = await client.getProject(params);
          setSelectedProject(result);
          break;
        case 'update_project':
          result = await client.updateProject(params);
          setUpdateDialogOpen(false);
          handleListProjects();
          break;
        case 'clone_project':
          result = await client.cloneProject(params);
          setCloneDialogOpen(false);
          handleListProjects();
          break;
        case 'archive_project':
          if (window.confirm('Are you sure you want to archive this project?')) {
            result = await client.archiveProject(params);
            handleListProjects();
          }
          break;
        case 'get_project_sessions':
          result = await client.getProjectSessions(params);
          setProjectSessions(result.sessions || []);
          break;
        case 'set_project_active_session':
          result = await client.setProjectActiveSession(params);
          if (selectedProject) {
            handleGetProject(selectedProject.id);
          }
          break;
        case 'create_project_checkpoint':
          result = await client.createProjectCheckpoint(params);
          break;
      }
      setResponse(result);
    } catch (err: any) {
      setError(err.message || 'Unknown error occurred');
    } finally {
      setLoading(null);
    }
  };

  const handleListProjects = () => {
    handleToolCall('list_projects');
  };

  const handleGetProject = (projectId: string) => {
    handleToolCall('get_project', { project_id: projectId });
    handleToolCall('get_project_sessions', { project_id: projectId });
  };

  const handleCreateProject = () => {
    try {
      const metadata = JSON.parse(createParams.metadata);
      handleToolCall('create_project', {
        name: createParams.name,
        path: createParams.path,
        description: createParams.description,
        metadata
      });
    } catch (err) {
      setError('Invalid JSON in metadata field');
    }
  };

  const handleUpdateProject = () => {
    if (!selectedProject) return;
    try {
      const metadata = JSON.parse(updateParams.metadata);
      handleToolCall('update_project', {
        project_id: selectedProject.id,
        updates: {
          name: updateParams.name || selectedProject.name,
          description: updateParams.description || selectedProject.description,
          metadata
        }
      });
    } catch (err) {
      setError('Invalid JSON in metadata field');
    }
  };

  const handleCloneProject = () => {
    if (!selectedProject) return;
    handleToolCall('clone_project', {
      project_id: selectedProject.id,
      new_name: cloneParams.targetPath.split('/').pop() || 'cloned-project',
      new_path: cloneParams.targetPath
    });
  };

  const renderProjectCard = (project: any) => (
    <Card key={project.id} sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
          <Box>
            <Typography variant="h6" component="div">
              {project.name}
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {project.path}
            </Typography>
            {project.description && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                {project.description}
              </Typography>
            )}
            <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {project.status && (
                <Chip 
                  label={project.status} 
                  size="small" 
                  color={project.status === 'active' ? 'success' : 'default'}
                  icon={project.status === 'active' ? <CheckCircle /> : <Archive />}
                />
              )}
              {project.activeSessionId && (
                <Chip 
                  label={`Session: ${project.activeSessionId}`} 
                  size="small" 
                  color="primary"
                  variant="outlined"
                />
              )}
              {project.sessionCount !== undefined && (
                <Chip 
                  label={`${project.sessionCount} sessions`} 
                  size="small" 
                  variant="outlined"
                />
              )}
            </Box>
          </Box>
        </Box>
      </CardContent>
      <CardActions>
        <Button 
          size="small" 
          onClick={() => handleGetProject(project.id)}
          startIcon={<Info />}
        >
          Details
        </Button>
        <Button 
          size="small" 
          onClick={() => {
            setUpdateParams({
              name: project.name,
              description: project.description || '',
              metadata: JSON.stringify(project.metadata || {}, null, 2)
            });
            setSelectedProject(project);
            setUpdateDialogOpen(true);
          }}
          startIcon={<Edit />}
        >
          Update
        </Button>
        <Button 
          size="small" 
          onClick={() => {
            setSelectedProject(project);
            setCloneParams({
              sourcePath: project.path,
              targetPath: '',
              includeHistory: true
            });
            setCloneDialogOpen(true);
          }}
          startIcon={<FileCopy />}
        >
          Clone
        </Button>
        <Button 
          size="small" 
          onClick={() => handleToolCall('archive_project', { project_id: project.id })}
          startIcon={<Archive />}
          color="warning"
        >
          Archive
        </Button>
      </CardActions>
    </Card>
  );

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Project Management Tools
      </Typography>
      
      <Grid container spacing={3}>
        {/* Tool Buttons */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Grid container spacing={2}>
              <Grid item>
                <Button
                  variant="contained"
                  startIcon={<CreateNewFolder />}
                  onClick={() => setCreateDialogOpen(true)}
                  disabled={loading === 'create_project'}
                >
                  Create Project
                </Button>
              </Grid>
              <Grid item>
                <Button
                  variant="contained"
                  startIcon={<ListIcon />}
                  onClick={handleListProjects}
                  disabled={loading === 'list_projects'}
                >
                  {loading === 'list_projects' ? <CircularProgress size={24} /> : 'List Projects'}
                </Button>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Projects List */}
        {projects.length > 0 && (
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Projects ({projects.length})
              </Typography>
              <Box sx={{ maxHeight: 600, overflow: 'auto' }}>
                {projects.map(renderProjectCard)}
              </Box>
            </Paper>
          </Grid>
        )}

        {/* Selected Project Details */}
        {selectedProject && (
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Project Details: {selectedProject.name}
              </Typography>
              
              <Box sx={{ mb: 3 }}>
                <ReactJson 
                  src={selectedProject} 
                  theme="monokai" 
                  collapsed={1}
                  displayDataTypes={false}
                />
              </Box>

              <Divider sx={{ my: 2 }} />

              {/* Project Sessions */}
              <Typography variant="subtitle1" gutterBottom>
                Sessions ({projectSessions.length})
              </Typography>
              <List>
                {projectSessions.map((session: any) => (
                  <ListItem key={session.id} divider>
                    <ListItemText
                      primary={`Session ${session.id}`}
                      secondary={
                        <Box>
                          <Typography variant="caption" display="block">
                            Status: {session.status}
                          </Typography>
                          {session.created_at && (
                            <Typography variant="caption" display="block">
                              Created: {new Date(session.created_at).toLocaleString()}
                            </Typography>
                          )}
                        </Box>
                      }
                    />
                    <ListItemSecondaryAction>
                      <Tooltip title="Set as Active Session">
                        <IconButton
                          onClick={() => handleToolCall('set_project_active_session', {
                            project_id: selectedProject.id,
                            session_id: session.id
                          })}
                          disabled={loading === 'set_project_active_session' || selectedProject.activeSessionId === session.id}
                        >
                          <PlayArrow color={selectedProject.activeSessionId === session.id ? 'primary' : 'inherit'} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Create Checkpoint">
                        <IconButton
                          onClick={() => handleToolCall('create_project_checkpoint', {
                            project_id: selectedProject.id,
                            name: `Checkpoint for session ${session.id}`,
                            description: `Automatically created checkpoint for session ${session.id}`,
                            include_sessions: true
                          })}
                        >
                          <Save />
                        </IconButton>
                      </Tooltip>
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

      {/* Create Project Dialog */}
      <Dialog 
        open={createDialogOpen} 
        onClose={() => setCreateDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create New Project</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label="Project Name"
              value={createParams.name}
              onChange={(e) => setCreateParams({ ...createParams, name: e.target.value })}
              margin="normal"
              required
            />
            <TextField
              fullWidth
              label="Project Path"
              value={createParams.path}
              onChange={(e) => setCreateParams({ ...createParams, path: e.target.value })}
              margin="normal"
              required
              helperText="Absolute path to the project directory"
            />
            <TextField
              fullWidth
              label="Description"
              value={createParams.description}
              onChange={(e) => setCreateParams({ ...createParams, description: e.target.value })}
              margin="normal"
              multiline
              rows={2}
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
            onClick={handleCreateProject} 
            variant="contained"
            disabled={loading === 'create_project' || !createParams.name || !createParams.path}
          >
            {loading === 'create_project' ? <CircularProgress size={24} /> : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Update Project Dialog */}
      <Dialog 
        open={updateDialogOpen} 
        onClose={() => setUpdateDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Update Project</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label="Project Name"
              value={updateParams.name}
              onChange={(e) => setUpdateParams({ ...updateParams, name: e.target.value })}
              margin="normal"
            />
            <TextField
              fullWidth
              label="Description"
              value={updateParams.description}
              onChange={(e) => setUpdateParams({ ...updateParams, description: e.target.value })}
              margin="normal"
              multiline
              rows={2}
            />
            <TextField
              fullWidth
              label="Metadata (JSON)"
              value={updateParams.metadata}
              onChange={(e) => setUpdateParams({ ...updateParams, metadata: e.target.value })}
              margin="normal"
              multiline
              rows={3}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUpdateDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={handleUpdateProject} 
            variant="contained"
            disabled={loading === 'update_project'}
          >
            {loading === 'update_project' ? <CircularProgress size={24} /> : 'Update'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Clone Project Dialog */}
      <Dialog 
        open={cloneDialogOpen} 
        onClose={() => setCloneDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Clone Project</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label="Source Path"
              value={cloneParams.sourcePath}
              onChange={(e) => setCloneParams({ ...cloneParams, sourcePath: e.target.value })}
              margin="normal"
              disabled
            />
            <TextField
              fullWidth
              label="Target Path"
              value={cloneParams.targetPath}
              onChange={(e) => setCloneParams({ ...cloneParams, targetPath: e.target.value })}
              margin="normal"
              required
              helperText="New path for the cloned project"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={cloneParams.includeHistory}
                  onChange={(e) => setCloneParams({ ...cloneParams, includeHistory: e.target.checked })}
                />
              }
              label="Include History"
              sx={{ mt: 2 }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCloneDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={handleCloneProject} 
            variant="contained"
            disabled={loading === 'clone_project' || !cloneParams.targetPath}
          >
            {loading === 'clone_project' ? <CircularProgress size={24} /> : 'Clone'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ProjectManagement;