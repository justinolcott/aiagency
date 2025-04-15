'use client';
import { useEffect, useState } from 'react';

export default function Home() {
  const [states, setStates] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/agency/states')
      .then(res => res.json())
      .then(data => {
        setStates(data.states || []);
        setLoading(false);
      });
  }, []);

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold mb-4">Agency Conversations</h1>
      <a href="/active" className="text-blue-600 underline mb-4 block">Go to Active Agency</a>
      <button
        className="bg-green-600 text-white px-4 py-2 rounded mb-4"
        onClick={async () => {
          await fetch('http://localhost:8000/agency/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
          window.location.href = '/active';
        }}
      >
        Start New Agency
      </button>
      <h2 className="text-xl font-semibold mt-6 mb-2">Past Agency States</h2>
      {loading ? <p>Loading...</p> : (
        <ul>
          {states.map(file => (
            <li key={file}>
              <a className="text-blue-600 underline" href={`/state/${encodeURIComponent(file)}`}>{file}</a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
