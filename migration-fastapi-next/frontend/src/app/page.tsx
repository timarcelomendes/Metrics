'use client';

import { useState } from 'react';
import { setUserEmail } from '@/lib/api';

export default function HomePage() {
  const [email, setEmail] = useState('');

  return (
    <section className="card stack">
      <h1>Gauge Metrics — Next.js + FastAPI</h1>
      <p>
        Base de migração focada em Jira: conexões, permissões, carregamento de projetos e construtor de gráficos.
      </p>
      <div className="row">
        <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="seu-email@empresa.com" />
        <button onClick={() => setUserEmail(email)}>Definir usuário da sessão</button>
      </div>
      <small>
        Durante a migração, este e-mail substitui o session_state do Streamlit e é enviado no header X-User-Email.
      </small>
    </section>
  );
}
