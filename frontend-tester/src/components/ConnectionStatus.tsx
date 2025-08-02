import React from 'react';
import { Box, Chip, IconButton, Tooltip } from '@mui/material';
import { Refresh, CheckCircle, Error } from '@mui/icons-material';

interface ConnectionStatusProps {
  connected: boolean;
  connecting: boolean;
  onConnect: () => void;
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  connected,
  connecting,
  onConnect,
}) => {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Chip
        icon={connected ? <CheckCircle /> : <Error />}
        label={connected ? 'Connected' : 'Disconnected'}
        color={connected ? 'success' : 'error'}
        variant="outlined"
      />
      <Tooltip title="Reconnect">
        <IconButton
          color="inherit"
          onClick={onConnect}
          disabled={connecting}
          size="small"
        >
          <Refresh />
        </IconButton>
      </Tooltip>
    </Box>
  );
};

export default ConnectionStatus;