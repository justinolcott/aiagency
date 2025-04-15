'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { use } from 'react';

export default function StateFilePage(props: { params: Promise<{ state_file: string }> }) {
    const params = use(props.params); // Unwrap the params Promise
    const [state, setState] = useState<any>(null);
    const [showDetails, setShowDetails] = useState(false);

    useEffect(() => {
        fetch(`http://localhost:8000/agency/state/${params.state_file}`)
            .then(res => res.json())
            .then(setState);
    }, [params.state_file]);

    if (!state) return <div className="p-8">Loading...</div>;

    return (
        <main className="p-8">
            <h1 className="text-2xl font-bold mb-4">Agency State: {params.state_file}</h1>
            <div className="mb-4">
                <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={showDetails}
                        onChange={(e) => setShowDetails(e.target.checked)}
                        className="h-4 w-4"
                    />
                    <span>Show tool calls and returns (applies to agent pages)</span>
                </label>
            </div>
            <h2 className="text-xl font-semibold mb-2">Agents</h2>
            <ul>
                {state.agents.map((agent: any) => {
                    console.log('Agent:', agent); // Debug log
                    return (
                        <li key={typeof agent.id === 'object' ? JSON.stringify(agent.id) : agent.id}>
                            <Link className="text-blue-600 underline"
                                href={`/state/${params.state_file}/agent/${typeof agent.id === 'object' ? JSON.stringify(agent.id) : agent.id}${showDetails ? '?details=true' : ''}`}>
                                {typeof agent.name === 'object' ? JSON.stringify(agent.name) : agent.name} (ID: {typeof agent.id === 'object' ? JSON.stringify(agent.id) : agent.id})
                            </Link>
                        </li>
                    );
                })}
            </ul>
            <Link className="block mt-4 text-gray-600 underline" href="/">Back to all conversations</Link>
        </main>
    );
}
