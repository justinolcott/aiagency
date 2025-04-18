'use client';
import { useEffect, useState } from 'react';

export default function ActiveAgencyPage() {
    const [agency, setAgency] = useState<any>(null);
    const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const [response, setResponse] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    // Fetch active agency state
    useEffect(() => {
        fetch('http://localhost:8000/agency/state')
            .then(res => res.json())
            .then(setAgency);
    }, [response]);

    if (!agency) return <div className="p-8">Loading...</div>;

    const agents = agency.agents || [];

    return (
        <main className="p-8">
            <h1 className="text-2xl font-bold mb-4">Active Agency</h1>
            <button
                className="bg-red-600 text-white px-4 py-2 rounded mb-4"
                onClick={async () => {
                    await fetch('http://localhost:8000/agency/stop', { method: 'POST' });
                    window.location.href = '/';
                }}
            >
                Stop Agency
            </button>
            <h2 className="text-xl font-semibold mb-2">Agents</h2>
            <ul>
                {agents.map((agent: any) => (
                    <li key={agent.id}>
                        <button
                            className={`underline ${selectedAgent === agent.id ? 'font-bold' : ''}`}
                            onClick={() => setSelectedAgent(agent.id)}
                        >
                            {agent.name} (ID: {agent.id})
                        </button>
                    </li>
                ))}
            </ul>
            {selectedAgent && (
                <div className="mt-6">
                    <h3 className="text-lg font-semibold mb-2">Agent Chat (ID: {selectedAgent})</h3>
                    <AgentChat agentId={selectedAgent} />
                </div>
            )}
            <a className="block mt-4 text-gray-600 underline" href="/">Back to all conversations</a>
        </main>
    );
}

function AgentChat({ agentId }: { agentId: string }) {
    const [agent, setAgent] = useState<any>(null);
    const [message, setMessage] = useState('');
    const [sending, setSending] = useState(false);
    const [chat, setChat] = useState<any[]>([]);
    const [showDetails, setShowDetails] = useState(false);

    // Fetch agent state
    useEffect(() => {
        fetch(`http://localhost:8000/agent/${agentId}/state`)
            .then(res => res.json())
            .then(agent => {
                setAgent(agent);
                setChat(agent.message_history || []);
            });
    }, [agentId]);

    const sendMessage = async () => {
        setSending(true);
        const res = await fetch(`http://localhost:8000/agent/${agentId}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
        });
        const data = await res.json();
        setMessage('');
        setSending(false);
        // Re-fetch agent state to update chat
        fetch(`http://localhost:8000/agent/${agentId}/state`)
            .then(res => res.json())
            .then(agent => setChat(agent.message_history || []));
    };

    if (!agent) return <div>Loading agent...</div>;

    return (
        <div>
            <div className="mb-2">
                <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={showDetails}
                        onChange={(e) => setShowDetails(e.target.checked)}
                        className="h-4 w-4"
                    />
                    <span>Show tool calls and returns</span>
                </label>
            </div>
            <div className="bg-gray-100 p-4 rounded max-h-[40vh] overflow-y-auto mb-2">
                {chat.map((msg: any, i: number) => (
                    <div key={i} className="mb-4 border-b pb-2">
                        <div className="text-xs font-medium text-black">{msg.kind || msg.__typename}</div>
                        {msg.parts && msg.parts.map((part: any, j: number) => (
                            <div key={j} className="mb-2">
                                {/* Message text content */}
                                {part.content && !part.tool_name && (
                                    <div className="pl-2 text-black whitespace-pre-wrap">
                                        {typeof part.content === 'object' ? JSON.stringify(part.content, null, 2) : part.content}
                                    </div>
                                )}

                                {/* Tool calls - only show if showDetails is true */}
                                {showDetails && part.tool_name && part.part_kind === "tool-call" && (
                                    <div className="pl-2 mt-1 mb-1">
                                        <div className="text-blue-600 font-medium">Tool Call: {part.tool_name}</div>
                                        {part.args && (
                                            <pre className="bg-gray-200 p-2 rounded text-sm overflow-x-auto text-black">
                                                {typeof part.args === 'object'
                                                    ? JSON.stringify(part.args, null, 2)
                                                    : part.args}
                                            </pre>
                                        )}
                                        <div className="text-xs text-gray-500">ID: {part.tool_call_id}</div>
                                    </div>
                                )}

                                {/* Tool returns - only show if showDetails is true */}
                                {showDetails && part.tool_name && part.part_kind === "tool-return" && (
                                    <div className="pl-2 mt-1 mb-1">
                                        <div className="text-green-600 font-medium">Tool Return: {part.tool_name}</div>
                                        <div className="bg-gray-200 p-2 rounded text-sm whitespace-pre-wrap overflow-x-auto text-black">
                                            {typeof part.content === 'object' ? JSON.stringify(part.content, null, 2) : part.content}
                                        </div>
                                        <div className="text-xs text-gray-500">ID: {part.tool_call_id}</div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                ))}
            </div>
            <form
                className="flex gap-2"
                onSubmit={e => {
                    e.preventDefault();
                    sendMessage();
                }}
            >
                <input
                    className="flex-1 border px-2 py-1 rounded"
                    value={message}
                    onChange={e => setMessage(e.target.value)}
                    placeholder="Type a message..."
                    disabled={sending}
                />
                <button
                    className="bg-blue-600 text-white px-4 py-1 rounded"
                    type="submit"
                    disabled={sending || !message}
                >
                    Send
                </button>
            </form>
        </div>
    );
}
