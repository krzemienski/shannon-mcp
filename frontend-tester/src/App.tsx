import React, { useState, useEffect } from 'react';
import {
  Container,
  AppBar,
  Toolbar,
  Typography,
  Box,
  Paper,
  Tabs,
  Tab,
  Alert,
  Chip,
  CircularProgress
} from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

// Import tool category components
import BinaryManagement from './components/BinaryManagement';
import SessionManagement from './components/SessionManagement';
import AgentManagement from './components/AgentManagement';
import CheckpointManagement from './components/CheckpointManagement';
import AnalyticsSettings from './components/AnalyticsSettings';
import ProjectManagement from './components/ProjectManagement';
import MCPServerManagement from './components/MCPServerManagement';
import ConnectionStatus from './components/ConnectionStatus';

import MCPClient from './services/MCPClient';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#f48fb1',
    },
  },
});

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`tool-tabpanel-${index}`}
      aria-labelledby={`tool-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

function App() {
  const [mcpClient] = useState(() => new MCPClient());
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [toolCount] = useState(30);

  useEffect(() => {
    // Set up connection handlers
    mcpClient.setConnectionChangeHandler((isConnected) => {
      setConnected(isConnected);
      setConnecting(false);
      if (isConnected) {
        setError(null);
      }
    });

    // Auto-connect on mount
    handleConnect();

    return () => {
      mcpClient.disconnect();
    };
  }, []);

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      await mcpClient.connect();
    } catch (err) {
      setError(`Failed to connect: ${err}`);
      setConnecting(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ flexGrow: 1 }}>
        <AppBar position="static">
          <Toolbar>
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              Shannon MCP Frontend Tester
            </Typography>
            <Chip
              label={`${toolCount} Tools`}
              color="secondary"
              sx={{ mr: 2 }}
            />
            <ConnectionStatus
              connected={connected}
              connecting={connecting}
              onConnect={handleConnect}
            />
          </Toolbar>
        </AppBar>

        <Container maxWidth="xl" sx={{ mt: 4 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {connecting && (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          )}

          {connected && (
            <Paper sx={{ width: '100%' }}>
              <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                <Tabs
                  value={tabValue}
                  onChange={handleTabChange}
                  variant="scrollable"
                  scrollButtons="auto"
                  aria-label="MCP tool categories"
                >
                  <Tab label="Binary (2)" />
                  <Tab label="Sessions (4)" />
                  <Tab label="Agents (4)" />
                  <Tab label="Checkpoints (4)" />
                  <Tab label="Analytics & Settings (3)" />
                  <Tab label="Projects (9)" />
                  <Tab label="MCP Servers (4)" />
                </Tabs>
              </Box>

              <TabPanel value={tabValue} index={0}>
                <BinaryManagement client={mcpClient} />
              </TabPanel>
              <TabPanel value={tabValue} index={1}>
                <SessionManagement client={mcpClient} />
              </TabPanel>
              <TabPanel value={tabValue} index={2}>
                <AgentManagement client={mcpClient} />
              </TabPanel>
              <TabPanel value={tabValue} index={3}>
                <CheckpointManagement client={mcpClient} />
              </TabPanel>
              <TabPanel value={tabValue} index={4}>
                <AnalyticsSettings client={mcpClient} />
              </TabPanel>
              <TabPanel value={tabValue} index={5}>
                <ProjectManagement client={mcpClient} />
              </TabPanel>
              <TabPanel value={tabValue} index={6}>
                <MCPServerManagement client={mcpClient} />
              </TabPanel>
            </Paper>
          )}
        </Container>
      </Box>
    </ThemeProvider>
  );
}

export default App;