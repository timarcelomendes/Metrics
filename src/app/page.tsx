'use client';

import { useState } from 'react';
import { setUserEmail } from '@/lib/api';

export default function HomePage() {
  const [email, setEmail] = useState('');

  return (
    <section className="card stack">
      <h1>Gauge Metrics</h1>
      <p>Base Next.js focada em Jira, permissões e construtor de gráficos.</p>
      <div className="row">
        <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="seu-email@empresa.com" />
        <button onClick={() => setUserEmail(email)}>Definir usuário</button>
      </div>
      <small>Este login é temporário para migração. Depois será substituído por autenticação oficial.</small>
    </section>
  );
}
