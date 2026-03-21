import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { AuthProvider, useAuth } from './context/AuthContext';
import { SessionProvider } from './context/SessionContext';
import { JobsProvider } from './context/JobsContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import BrokerConnectionsPage from './pages/BrokerConnectionsPage';
import SessionsPage from './pages/SessionsPage';
import HoldingsPage from './pages/HoldingsPage';
import BuyEntriesPage from './pages/BuyEntriesPage';
import EntryStrategiesPage from './pages/EntryStrategiesPage';
import StrategyDetailPage from './pages/StrategyDetailPage';
import PlanPage from './pages/PlanPage';
import GTTPage from './pages/GTTPage';
import JobsPage from './pages/JobsPage';
import AdminPage from './pages/AdminPage';

const theme = createTheme({
  palette: {
    mode: 'light',
  },
});

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return null;
  }

  return user ? <>{children}</> : <Navigate to="/login" />;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return null;
  }

  return user ? <Navigate to="/dashboard" /> : <>{children}</>;
}

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <AuthProvider>
          <SessionProvider>
            <JobsProvider>
              <Routes>
                <Route
                  path="/login"
                  element={
                    <PublicRoute>
                      <LoginPage />
                    </PublicRoute>
                  }
                />
                <Route
                  path="/register"
                  element={
                    <PublicRoute>
                      <RegisterPage />
                    </PublicRoute>
                  }
                />
                <Route
                  path="/dashboard"
                  element={
                    <PrivateRoute>
                      <Layout>
                        <DashboardPage />
                      </Layout>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/broker-connections"
                  element={
                    <PrivateRoute>
                      <Layout>
                        <BrokerConnectionsPage />
                      </Layout>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/sessions"
                  element={
                    <PrivateRoute>
                      <Layout>
                        <SessionsPage />
                      </Layout>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/holdings"
                  element={
                    <PrivateRoute>
                      <Layout>
                        <HoldingsPage />
                      </Layout>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/entries"
                  element={
                    <PrivateRoute>
                      <Layout>
                        <BuyEntriesPage />
                      </Layout>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/entry-strategies"
                  element={
                    <PrivateRoute>
                      <Layout>
                        <EntryStrategiesPage />
                      </Layout>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/entry-strategies/:symbol"
                  element={
                    <PrivateRoute>
                      <Layout>
                        <StrategyDetailPage />
                      </Layout>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/plan"
                  element={
                    <PrivateRoute>
                      <Layout>
                        <PlanPage />
                      </Layout>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/gtt"
                  element={
                    <PrivateRoute>
                      <Layout>
                        <GTTPage />
                      </Layout>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/jobs"
                  element={
                    <PrivateRoute>
                      <Layout>
                        <JobsPage />
                      </Layout>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/admin"
                  element={
                    <PrivateRoute>
                      <Layout>
                        <AdminPage />
                      </Layout>
                    </PrivateRoute>
                  }
                />
                <Route path="/" element={<Navigate to="/dashboard" />} />
              </Routes>
            </JobsProvider>
          </SessionProvider>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
