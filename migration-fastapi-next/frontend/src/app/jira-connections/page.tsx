'use client';

import { FormEvent, useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import type { JiraConnection } from '@/types';

export default function JiraConnectionsPage() {
  const [connections, setConnections] = useState<JiraConnection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadConnections() {
    setError(null);
    const data = await apiFetch<JiraConnection[]>('/api/jira/connections');
    setConnections(data);
  }

  useEffect(() => {
    loadConnections().catch((err) => setError(err.message));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    try {
      await apiFetch('/api/jira/connections', {
        method: 'POST',
        body: JSON.stringify({
          name: form.get('name'),
          jira_url: form.get('jira_url'),
          jira_email: form.get('jira_email'),
          api_token: form.get('api_token'),
        }),
      });
      event.currentTarget.reset();
      await loadConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar conexão');
    } finally {
      setLoading(false);
    }
  }

  async function activate(connectionId: string) {
    setError(null);
    await apiFetch('/api/jira/connections/activate', {
      method: 'POST',
      body: JSON.stringify({ connection_id: connectionId }),
    });
    await loadConnections();
  }

  return (
    <div className="stack">
      <section className="card stack">
        <h1>Conexões Jira</h1>
        <p>Substitui a página Streamlit de conexões, mantendo token criptografado e validação antes de ativar.</p>
        {error && <strong>{error}</strong>}
        <form onSubmit={submit} className="grid">
          <input name="name" placeholder="Nome da conexão" required />
          <input name="jira_url" placeholder="https://empresa.atlassian.net" required />
          <input name="jira_email" placeholder="E-mail do Jira" required />
          <input name="api_token" placeholder="Token de API" type="password" required />
          <button disabled={loading}>{loading ? 'Salvando...' : 'Testar e salvar conexão'}</button>
        </form>
      </section>

      <section className="card stack">
        <h2>Conexões salvas</h2>
        {connections.map((connection) => (
          <div key={connection.id} className="row">
            <strong>{connection.name}</strong>
            <span>{connection.jira_url}</span>
            <span>{connection.jira_email}</span>
            <span>{connection.active ? '🟢 Ativa' : 'Inativa'}</span>
            {!connection.active && <button onClick={() => activate(connection.id)}>Ativar</button>}
          </div>
        ))}
      </section>
    </div>
  );
}
