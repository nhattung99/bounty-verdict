import React, { useState, useEffect } from 'react';
import { createClient, chains } from 'genlayer-js';
import {
  ShieldAlert,
  ShieldCheck,
  PlusCircle,
  FileCode2,
  ListFilter,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  Wallet,
  RefreshCw,
  Cpu,
  Lock,
  Award,
  Zap,
  Coins
} from 'lucide-react';

const REGISTRY_ADDRESS = import.meta.env.VITE_BOUNTY_REGISTRY_ADDRESS || '0x062E0e565Ef38431C6097f11697D37e97c2CdFc0';
const VERDICT_ADDRESS = import.meta.env.VITE_BOUNTY_VERDICT_ADDRESS || '0x76791569a919364D9B6c8a371a6F9FB79191e68E';

const studionet = chains.studionet;

// Module-level read client
const readClient = createClient({ chain: studionet });

// Write client factory
const getWriteClient = (account) =>
  createClient({
    chain: studionet,
    account,
    provider: window.ethereum
  });

export default function App() {
  const [account, setAccount] = useState(null);
  const [activeTab, setActiveTab] = useState('programs');

  // Data states
  const [programs, setPrograms] = useState([]);
  const [reports, setReports] = useState([]);
  const [selectedReportId, setSelectedReportId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [txHash, setTxHash] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [depositProgramId, setDepositProgramId] = useState('');
  const [depositValue, setDepositValue] = useState('100');

  // Form states
  const [newProgram, setNewProgram] = useState({
    protocol_name: '',
    scope_url: '',
    payout_critical: '1000',
    payout_high: '500',
    payout_medium: '200',
    payout_low: '50',
    deposit_amount: '3000'
  });

  const [newReport, setNewReport] = useState({
    program_id: '',
    affected_component: '',
    vulnerability_type: 'Reentrancy',
    description: '',
    poc_url: '',
    additional_url: ''
  });

  // Connect Wallet
  const connectWallet = async () => {
    try {
      if (!window.ethereum) {
        alert('MetaMask is required to interact with BountyVerdict.');
        return;
      }
      setErrorMessage(null);
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
      const addr = accounts[0];
      const tempClient = createClient({ chain: studionet, account: addr, provider: window.ethereum });
      await tempClient.connect('studionet');
      setAccount(addr);
    } catch (err) {
      console.error('Wallet connection error:', err);
      setErrorMessage(err?.message || 'Failed to connect wallet');
    }
  };

  // Fetch Programs from BountyRegistry
  const fetchPrograms = async () => {
    if (!REGISTRY_ADDRESS || REGISTRY_ADDRESS === '0x0000000000000000000000000000000000000000') return;
    try {
      setLoading(true);
      const res = await readClient.readContract({
        address: REGISTRY_ADDRESS,
        functionName: 'list_programs',
        args: ['']
      });
      const data = JSON.parse(res || '[]');
      setPrograms(data);
    } catch (err) {
      console.error('Fetch programs error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch Reports from BountyVerdict
  const fetchReports = async () => {
    if (!VERDICT_ADDRESS || VERDICT_ADDRESS === '0x0000000000000000000000000000000000000000') return;
    try {
      setLoading(true);
      const res = await readClient.readContract({
        address: VERDICT_ADDRESS,
        functionName: 'list_reports',
        args: ['', '']
      });
      const data = JSON.parse(res || '[]');
      setReports(data);
    } catch (err) {
      console.error('Fetch reports error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPrograms();
    fetchReports();
  }, []);

  // Create Program & Deposit Escrow
  const handleCreateProgram = async (e) => {
    e.preventDefault();
    if (!account) {
      alert('Please connect your wallet first.');
      return;
    }
    try {
      setLoading(true);
      setErrorMessage(null);
      setTxHash(null);

      const client = getWriteClient(account);

      // 1. Create Program
      const tx1 = await client.writeContract({
        address: REGISTRY_ADDRESS,
        functionName: 'create_program',
        args: [
          newProgram.protocol_name,
          newProgram.scope_url,
          parseInt(newProgram.payout_critical),
          parseInt(newProgram.payout_high),
          parseInt(newProgram.payout_medium),
          parseInt(newProgram.payout_low)
        ]
      });

      setTxHash(tx1);
      await fetchPrograms();

      // 2. Deposit Payable Escrow Value
      if (parseFloat(newProgram.deposit_amount) > 0) {
        const countRes = await readClient.readContract({
          address: REGISTRY_ADDRESS,
          functionName: 'get_program_count',
          args: []
        });
        const latestId = String(countRes);

        const tx2 = await client.writeContract({
          address: REGISTRY_ADDRESS,
          functionName: 'deposit_escrow',
          args: [latestId],
          value: BigInt(newProgram.deposit_amount) // Attached value for payable method
        });
        setTxHash(tx2);
      }

      await fetchPrograms();
      setActiveTab('programs');
    } catch (err) {
      console.error('Create program error:', err);
      setErrorMessage(err?.message || 'Transaction failed');
    } finally {
      setLoading(false);
    }
  };

  // Deposit Escrow Standalone (Payable Method)
  const handleDepositEscrow = async (programId, amount) => {
    if (!account) {
      alert('Please connect your wallet first.');
      return;
    }
    try {
      setLoading(true);
      setErrorMessage(null);
      setTxHash(null);

      const client = getWriteClient(account);
      const hash = await client.writeContract({
        address: REGISTRY_ADDRESS,
        functionName: 'deposit_escrow',
        args: [programId],
        value: BigInt(amount) // Non-zero attached value for payable method
      });

      setTxHash(hash);
      await fetchPrograms();
    } catch (err) {
      console.error('Deposit escrow error:', err);
      setErrorMessage(err?.message || 'Escrow deposit failed');
    } finally {
      setLoading(false);
    }
  };

  // Submit Report
  const handleSubmitReport = async (e) => {
    e.preventDefault();
    if (!account) {
      alert('Please connect your wallet first.');
      return;
    }
    try {
      setLoading(true);
      setErrorMessage(null);
      setTxHash(null);

      const client = getWriteClient(account);
      const hash = await client.writeContract({
        address: VERDICT_ADDRESS,
        functionName: 'submit_report',
        args: [
          newReport.program_id,
          newReport.affected_component,
          newReport.vulnerability_type,
          newReport.description,
          newReport.poc_url,
          newReport.additional_url
        ]
      });

      setTxHash(hash);
      await fetchReports();
      setActiveTab('my_reports');
    } catch (err) {
      console.error('Submit report error:', err);
      setErrorMessage(err?.message || 'Report submission failed');
    } finally {
      setLoading(false);
    }
  };

  // Evaluate Report (AI Consensus)
  const handleEvaluateReport = async (reportId) => {
    if (!account) {
      alert('Please connect your wallet to trigger evaluation.');
      return;
    }
    try {
      setEvaluating(true);
      setErrorMessage(null);
      setTxHash(null);

      const client = getWriteClient(account);
      const hash = await client.writeContract({
        address: VERDICT_ADDRESS,
        functionName: 'evaluate_report',
        args: [reportId]
      });

      setTxHash(hash);
      await fetchReports();
      await fetchPrograms();
    } catch (err) {
      console.error('Evaluate report error:', err);
      setErrorMessage(err?.message || 'Evaluation failed');
    } finally {
      setEvaluating(false);
    }
  };

  const selectedReport = reports.find((r) => r.report_id === selectedReportId);

  return (
    <div className="app-container">
      {/* App Header */}
      <header className="app-header">
        <div className="brand">
          <div className="brand-icon">
            <ShieldAlert size={24} />
          </div>
          <div>
            <h1 className="brand-title">BountyVerdict</h1>
            <span className="brand-tag">GenLayer AI Court</span>
          </div>
        </div>

        <div className="header-controls">
          <div className="network-badge">
            <span className="dot"></span>
            <span>studionet</span>
          </div>

          {account ? (
            <button className="btn-secondary mono">
              <Wallet size={16} />
              {account.substring(0, 6)}...{account.substring(account.length - 4)}
            </button>
          ) : (
            <button className="btn-primary" onClick={connectWallet}>
              <Wallet size={16} />
              Connect Wallet
            </button>
          )}
        </div>
      </header>

      {/* Nav Tabs */}
      <nav className="nav-tabs">
        <button
          className={`tab-btn ${activeTab === 'programs' ? 'active' : ''}`}
          onClick={() => setActiveTab('programs')}
        >
          <Award size={16} />
          Bounty Programs ({programs.length})
        </button>

        <button
          className={`tab-btn ${activeTab === 'create_program' ? 'active' : ''}`}
          onClick={() => setActiveTab('create_program')}
        >
          <PlusCircle size={16} />
          Create Program
        </button>

        <button
          className={`tab-btn ${activeTab === 'submit_report' ? 'active' : ''}`}
          onClick={() => setActiveTab('submit_report')}
        >
          <FileCode2 size={16} />
          Submit Report
        </button>

        <button
          className={`tab-btn ${activeTab === 'my_reports' ? 'active' : ''}`}
          onClick={() => setActiveTab('my_reports')}
        >
          <ListFilter size={16} />
          My Reports
        </button>

        {selectedReport && (
          <button className="tab-btn active">
            <Cpu size={16} />
            Report #{selectedReport.report_id} Detail
          </button>
        )}
      </nav>

      {/* Notification Banners */}
      {txHash && (
        <div className="tx-banner">
          <span>Transaction submitted successfully! TxHash: <strong className="mono">{txHash}</strong></span>
          <a
            href={`https://studio.genlayer.com/explorer`}
            target="_blank"
            rel="noopener noreferrer"
            className="link mono"
          >
            Explorer Tx <ExternalLink size={14} style={{ display: 'inline' }} />
          </a>
        </div>
      )}

      {errorMessage && <div className="error-banner">{errorMessage}</div>}

      {/* TAB 1: BOUNTY PROGRAMS */}
      {activeTab === 'programs' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
            <h2>Active Bounty Programs</h2>
            <button className="btn-secondary" onClick={fetchPrograms}>
              <RefreshCw size={14} /> Refresh
            </button>
          </div>

          {programs.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
              <Lock size={40} color="#64748b" style={{ marginBottom: '1rem' }} />
              <p style={{ color: 'var(--text-muted)' }}>No bounty programs registered yet.</p>
              <button
                className="btn-primary"
                style={{ marginTop: '1rem' }}
                onClick={() => setActiveTab('create_program')}
              >
                Create First Program
              </button>
            </div>
          ) : (
            <div className="grid-2">
              {programs.map((p) => (
                <div className="card" key={p.program_id}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <div>
                      <h3 style={{ fontSize: '1.2rem', marginBottom: '0.2rem' }}>{p.protocol_name}</h3>
                      <span className="mono" style={{ color: 'var(--text-sub)', fontSize: '0.8rem' }}>
                        Program #{p.program_id}
                      </span>
                    </div>
                    <span className={`badge badge-${p.status.toLowerCase()}`}>{p.status}</span>
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <span className="form-label">Scope URL:</span>
                    <a
                      href={p.scope_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="link mono"
                      style={{ fontSize: '0.85rem', wordBreak: 'break-all' }}
                    >
                      {p.scope_url} <ExternalLink size={12} style={{ display: 'inline' }} />
                    </a>
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <span className="form-label">Escrow Balance:</span>
                    <div style={{ display: 'flex', gap: '1rem', fontSize: '0.9rem' }}>
                      <div>
                        Deposited: <strong style={{ color: 'var(--accent-cyan)' }}>{p.total_deposited} GEN</strong>
                      </div>
                      <div>
                        Paid Out: <strong>{p.total_paid_out} GEN</strong>
                      </div>
                    </div>
                  </div>

                  <span className="form-label">Payout Tiers:</span>
                  <table className="payout-tier-table">
                    <thead>
                      <tr>
                        <th>Tier</th>
                        <th>Payout</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>
                          <span className="badge badge-sev-critical">CRITICAL</span>
                        </td>
                        <td className="mono">{p.payout_critical} GEN</td>
                      </tr>
                      <tr>
                        <td>
                          <span className="badge badge-sev-high">HIGH</span>
                        </td>
                        <td className="mono">{p.payout_high} GEN</td>
                      </tr>
                      <tr>
                        <td>
                          <span className="badge badge-sev-medium">MEDIUM</span>
                        </td>
                        <td className="mono">{p.payout_medium} GEN</td>
                      </tr>
                      <tr>
                        <td>
                          <span className="badge badge-sev-low">LOW</span>
                        </td>
                        <td className="mono">{p.payout_low} GEN</td>
                      </tr>
                    </tbody>
                  </table>

                  {/* Standalone Payable Escrow Deposit Button */}
                  <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
                    <button
                      className="btn-secondary"
                      style={{ width: '100%', justifyContent: 'center', marginBottom: '0.75rem' }}
                      onClick={() => handleDepositEscrow(p.program_id, '100')}
                    >
                      <Coins size={16} /> Deposit +100 GEN Escrow (Payable)
                    </button>

                    <button
                      className="btn-primary"
                      style={{ width: '100%', justifyContent: 'center' }}
                      onClick={() => {
                        setNewReport({ ...newReport, program_id: p.program_id });
                        setActiveTab('submit_report');
                      }}
                    >
                      Submit Vulnerability Report
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: CREATE PROGRAM */}
      {activeTab === 'create_program' && (
        <div className="card" style={{ maxWidth: '650px', margin: '0 auto' }}>
          <h2 style={{ marginBottom: '1.5rem' }}>Create Bounty Program & Lock Scope</h2>

          <form onSubmit={handleCreateProgram}>
            <div className="form-group">
              <label className="form-label">Protocol / Project Name *</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Uniswap V4 Module"
                value={newProgram.protocol_name}
                onChange={(e) => setNewProgram({ ...newProgram, protocol_name: e.target.value })}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Official Scope Page URL (HTTP/HTTPS) *</label>
              <input
                type="url"
                className="form-input"
                placeholder="https://docs.protocol.io/security/bounty-scope"
                value={newProgram.scope_url}
                onChange={(e) => setNewProgram({ ...newProgram, scope_url: e.target.value })}
                required
              />
            </div>

            <h4 style={{ margin: '1.5rem 0 1rem', color: 'var(--accent-cyan)' }}>Payout Tiers Escrow (in GEN)</h4>

            <div className="grid-2" style={{ gap: '1rem', marginBottom: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Critical Tier Payout *</label>
                <input
                  type="number"
                  className="form-input"
                  value={newProgram.payout_critical}
                  onChange={(e) => setNewProgram({ ...newProgram, payout_critical: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">High Tier Payout *</label>
                <input
                  type="number"
                  className="form-input"
                  value={newProgram.payout_high}
                  onChange={(e) => setNewProgram({ ...newProgram, payout_high: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Medium Tier Payout *</label>
                <input
                  type="number"
                  className="form-input"
                  value={newProgram.payout_medium}
                  onChange={(e) => setNewProgram({ ...newProgram, payout_medium: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Low Tier Payout *</label>
                <input
                  type="number"
                  className="form-input"
                  value={newProgram.payout_low}
                  onChange={(e) => setNewProgram({ ...newProgram, payout_low: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Initial Escrow Deposit Value (GEN attached to Payable deposit_escrow)</label>
              <input
                type="number"
                className="form-input"
                value={newProgram.deposit_amount}
                onChange={(e) => setNewProgram({ ...newProgram, deposit_amount: e.target.value })}
              />
            </div>

            <button
              type="submit"
              className="btn-primary"
              disabled={loading}
              style={{ width: '100%', justifyContent: 'center', marginTop: '1rem' }}
            >
              {loading ? 'Deploying Program On-Chain...' : 'Create Program & Deposit Escrow'}
            </button>
          </form>
        </div>
      )}

      {/* TAB 3: SUBMIT REPORT */}
      {activeTab === 'submit_report' && (
        <div className="card" style={{ maxWidth: '700px', margin: '0 auto' }}>
          <h2 style={{ marginBottom: '1rem' }}>Submit Security Vulnerability Report</h2>

          <div className="callout-warning">
            <AlertTriangle size={24} style={{ shrink: 0 }} />
            <div>
              <strong>On-Chain AI Adjudication Notice:</strong>
              <p style={{ marginTop: '0.2rem' }}>
                Your report will be evaluated by GenLayer AI validators reading your PoC URL directly on-chain. Make sure your PoC URL (GitHub Gist, writeup) is publicly accessible.
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmitReport}>
            <div className="form-group">
              <label className="form-label">Target Bounty Program *</label>
              <select
                className="form-select"
                value={newReport.program_id}
                onChange={(e) => setNewReport({ ...newReport, program_id: e.target.value })}
                required
              >
                <option value="">Select a Program...</option>
                {programs
                  .filter((p) => p.status === 'ACTIVE')
                  .map((p) => (
                    <option key={p.program_id} value={p.program_id}>
                      #{p.program_id} - {p.protocol_name}
                    </option>
                  ))}
              </select>
            </div>

            <div className="grid-2" style={{ gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Affected Component *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. ERC20 Token Vault, Bridge Module"
                  value={newReport.affected_component}
                  onChange={(e) => setNewReport({ ...newReport, affected_component: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Vulnerability Type *</label>
                <select
                  className="form-select"
                  value={newReport.vulnerability_type}
                  onChange={(e) => setNewReport({ ...newReport, vulnerability_type: e.target.value })}
                >
                  <option value="Reentrancy">Reentrancy</option>
                  <option value="Integer Overflow">Integer Overflow</option>
                  <option value="Access Control">Access Control Bypass</option>
                  <option value="Logic Error">Logic Flaw</option>
                  <option value="Oracle Manipulation">Oracle Manipulation</option>
                  <option value="Frontrunning">Frontrunning / MEV</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Proof-of-Concept (PoC) Public URL *</label>
              <input
                type="url"
                className="form-input"
                placeholder="https://gist.github.com/hacker/poc-reentrancy-exploit"
                value={newReport.poc_url}
                onChange={(e) => setNewReport({ ...newReport, poc_url: e.target.value })}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Additional Reference URL (Optional)</label>
              <input
                type="url"
                className="form-input"
                placeholder="https://etherscan.io/address/0x..."
                value={newReport.additional_url}
                onChange={(e) => setNewReport({ ...newReport, additional_url: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Technical Description (Max 1000 characters) *</label>
              <textarea
                className="form-textarea"
                maxLength={1000}
                placeholder="Explain the step-by-step impact and how the PoC triggers the vulnerability..."
                value={newReport.description}
                onChange={(e) => setNewReport({ ...newReport, description: e.target.value })}
                required
              />
              <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-sub)', display: 'block', textAlign: 'right', marginTop: '0.2rem' }}>
                {newReport.description.length}/1000
              </span>
            </div>

            <button
              type="submit"
              className="btn-primary"
              disabled={loading}
              style={{ width: '100%', justifyContent: 'center', marginTop: '1rem' }}
            >
              {loading ? 'Submitting Report On-Chain...' : 'Submit Vulnerability Report'}
            </button>
          </form>
        </div>
      )}

      {/* TAB 4: MY REPORTS & DETAIL */}
      {(activeTab === 'my_reports' || selectedReport) && (
        <div>
          {selectedReport ? (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h2>Vulnerability Report #{selectedReport.report_id}</h2>
                <button
                  className="btn-secondary"
                  onClick={() => setSelectedReportId(null)}
                >
                  Back to List
                </button>
              </div>

              {/* Status & Evaluation Hero Banner */}
              {evaluating ? (
                <div className="loading-box">
                  <div className="spinner"></div>
                  <h3 style={{ marginBottom: '0.5rem', color: 'var(--accent-cyan)' }}>
                    AI Consensus Evaluation in Progress
                  </h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    GenLayer AI validators are fetching PoC writeup and protocol scope page on-chain...
                  </p>
                  <div className="progress-bar-container">
                    <div className="progress-bar-fill"></div>
                  </div>
                  <span className="mono" style={{ fontSize: '0.8rem', color: 'var(--text-sub)' }}>
                    Expected duration: 30 - 120 seconds
                  </span>
                </div>
              ) : selectedReport.status === 'EVALUATED' ? (
                <div
                  className="card"
                  style={{
                    background: '#0e1626',
                    borderColor: 'var(--accent-blue)',
                    marginBottom: '2rem'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                    <div>
                      <span className="form-label">Ruling Severity Tier:</span>
                      <span className={`badge badge-sev-${selectedReport.severity.toLowerCase()}`} style={{ fontSize: '1rem', padding: '0.4rem 0.8rem' }}>
                        {selectedReport.severity}
                      </span>
                    </div>

                    <div>
                      <span className="form-label">In-Scope Assessment:</span>
                      {selectedReport.in_scope ? (
                        <span className="badge badge-active" style={{ fontSize: '0.9rem' }}>
                          <CheckCircle2 size={14} /> IN SCOPE
                        </span>
                      ) : (
                        <span className="badge badge-closed" style={{ fontSize: '0.9rem' }}>
                          <AlertTriangle size={14} /> OUT OF SCOPE
                        </span>
                      )}
                    </div>

                    <div>
                      <span className="form-label">Validator Confidence:</span>
                      <span className="mono" style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--accent-cyan)' }}>
                        {selectedReport.confidence}%
                      </span>
                    </div>
                  </div>

                  <div style={{ marginBottom: '1rem' }}>
                    <span className="form-label">AI Technical Reasoning:</span>
                    <p style={{ background: '#090d16', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)', fontSize: '0.95rem' }}>
                      "{selectedReport.reasoning}"
                    </p>
                  </div>

                  {selectedReport.paid_out && (
                    <div className="tx-banner" style={{ marginTop: '1rem' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Zap size={18} /> Escrow payout executed automatically to reporter address!
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <div
                  className="card"
                  style={{
                    background: '#161d2a',
                    display: 'flex',
                    justify: 'space-between',
                    alignItems: 'center',
                    marginBottom: '2rem'
                  }}
                >
                  <div>
                    <h4 style={{ color: 'var(--accent-cyan)', marginBottom: '0.25rem' }}>
                      Report Ready for AI Consensus Adjudication
                    </h4>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      Anyone can trigger the permissionless evaluation on-chain.
                    </p>
                  </div>

                  <button
                    className="btn-primary"
                    onClick={() => handleEvaluateReport(selectedReport.report_id)}
                  >
                    <Cpu size={16} /> Evaluate Report On-Chain
                  </button>
                </div>
              )}

              {/* Report Metadata */}
              <div className="grid-2">
                <div>
                  <span className="form-label">Reporter Address:</span>
                  <p className="mono" style={{ wordBreak: 'break-all', marginBottom: '1rem' }}>
                    {selectedReport.reporter}
                  </p>

                  <span className="form-label">Affected Component:</span>
                  <p style={{ marginBottom: '1rem' }}>{selectedReport.affected_component}</p>

                  <span className="form-label">Vulnerability Type:</span>
                  <p style={{ marginBottom: '1rem' }}>{selectedReport.vulnerability_type}</p>
                </div>

                <div>
                  <span className="form-label">Proof of Concept URL:</span>
                  <p style={{ marginBottom: '1rem' }}>
                    <a
                      href={selectedReport.poc_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="link mono"
                      style={{ wordBreak: 'break-all' }}
                    >
                      {selectedReport.poc_url} <ExternalLink size={12} style={{ display: 'inline' }} />
                    </a>
                  </p>

                  {selectedReport.additional_url && (
                    <>
                      <span className="form-label">Additional Reference:</span>
                      <p style={{ marginBottom: '1rem' }}>
                        <a
                          href={selectedReport.additional_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="link mono"
                          style={{ wordBreak: 'break-all' }}
                        >
                          {selectedReport.additional_url} <ExternalLink size={12} style={{ display: 'inline' }} />
                        </a>
                      </p>
                    </>
                  )}
                </div>
              </div>

              <div style={{ marginTop: '1rem' }}>
                <span className="form-label">Technical Description:</span>
                <div style={{ background: 'var(--bg-input)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)', whiteSpace: 'pre-wrap' }}>
                  {selectedReport.description}
                </div>
              </div>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                <h2>Submitted Vulnerability Reports</h2>
                <button className="btn-secondary" onClick={fetchReports}>
                  <RefreshCw size={14} /> Refresh
                </button>
              </div>

              {reports.length === 0 ? (
                <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
                  <FileCode2 size={40} color="#64748b" style={{ marginBottom: '1rem' }} />
                  <p style={{ color: 'var(--text-muted)' }}>No reports submitted yet.</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {reports.map((r) => (
                    <div
                      className="card"
                      key={r.report_id}
                      style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                      onClick={() => setSelectedReportId(r.report_id)}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.4rem' }}>
                          <h4 style={{ fontSize: '1.05rem' }}>
                            Report #{r.report_id} — {r.affected_component}
                          </h4>
                          <span className={`badge badge-${r.status.toLowerCase()}`}>
                            {r.status}
                          </span>
                        </div>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                          Type: {r.vulnerability_type} | Program #{r.program_id}
                        </p>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        {r.severity ? (
                          <span className={`badge badge-sev-${r.severity.toLowerCase()}`} style={{ fontSize: '0.85rem' }}>
                            {r.severity}
                          </span>
                        ) : (
                          <span className="mono" style={{ color: 'var(--text-sub)', fontSize: '0.85rem' }}>
                            Pending Evaluation
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
