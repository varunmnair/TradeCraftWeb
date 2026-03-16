import React, { useEffect, useState } from 'react';
import { Box, Typography, Grid, Paper, Card, CardContent, CardActionArea } from '@mui/material';
import {
  AccountBalance as BrokerIcon,
  PlayCircle as SessionIcon,
  Assessment as HoldingsIcon,
  Assignment as PlanIcon,
  Notifications as GttIcon,
  Work as JobsIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const quickLinks = [
  { text: 'Broker Connections', icon: <BrokerIcon sx={{ fontSize: 40 }} />, path: '/broker-connections', color: '#1976d2' },
  { text: 'Sessions', icon: <SessionIcon sx={{ fontSize: 40 }} />, path: '/sessions', color: '#388e3c' },
  { text: 'Holdings', icon: <HoldingsIcon sx={{ fontSize: 40 }} />, path: '/holdings', color: '#d32f2f' },
  { text: 'Plan', icon: <PlanIcon sx={{ fontSize: 40 }} />, path: '/plan', color: '#7b1fa2' },
  { text: 'GTT Orders', icon: <GttIcon sx={{ fontSize: 40 }} />, path: '/gtt', color: '#f57c00' },
  { text: 'Jobs', icon: <JobsIcon sx={{ fontSize: 40 }} />, path: '/jobs', color: '#00796b' },
];

export default function DashboardPage() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [lastRefresh, setLastRefresh] = useState(new Date());

  useEffect(() => {
    refreshUser();
    const interval = setInterval(() => setLastRefresh(new Date()), 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6">Current User</Typography>
        {user ? (
          <Box>
            <Typography>Email: {user.email}</Typography>
            <Typography>Role: {user.role}</Typography>
            <Typography>Tenant ID: {user.tenant_id}</Typography>
            <Typography variant="caption" color="text.secondary">
              Last refreshed: {lastRefresh.toLocaleTimeString()}
            </Typography>
          </Box>
        ) : (
          <Typography color="error">Not logged in</Typography>
        )}
      </Paper>

      <Typography variant="h6" gutterBottom>
        Quick Links
      </Typography>
      <Grid container spacing={3}>
        {quickLinks.map((item) => (
          <Grid item xs={12} sm={6} md={4} key={item.text}>
            <Card>
              <CardActionArea
                onClick={() => navigate(item.path)}
                sx={{ p: 2, textAlign: 'center' }}
              >
                <Box sx={{ color: item.color, mb: 1 }}>{item.icon}</Box>
                <CardContent>
                  <Typography variant="h6">{item.text}</Typography>
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
