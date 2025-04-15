'use client';
import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

export default function AgentStatePage(props: { params: Promise<{ state_file: string, agent_id: string }> }) {
    const params = use(props.params); // Unwrap the params Promise
    const searchParams = useSearchParams();
    const [agent, setAgent] = useState<any>(null);
    const [showDetails, setShowDetails] = useState(searchParams.get('details') === 'true');

    useEffect(() => {
        fetch(`http://localhost:8000/agency/state/${params.state_file}`)
            .then(res => res.json())
            .then(state => {
                const found = state.agents.find((a: any) => a.id === params.agent_id);
                setAgent(found);
            });
    }, [params.state_file, params.agent_id]);

    if (!agent) return <div className="p-8">Loading...</div>;

    return (
        <main className="p-8">
            <h1 className="text-2xl font-bold mb-4">{agent.name} (ID: {agent.id})</h1>
            <div className="mb-4">
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
            <h2 className="text-xl font-semibold mb-2">Message History</h2>
            <div className="bg-gray-100 p-4 rounded max-h-[60vh] overflow-y-auto">
                {agent.message_history.map((msg: any, i: number) => (
                    <div key={i} className="mb-4 border-b pb-2">
                        <div className="text-xs font-semibold text-black mb-1">{msg.kind || msg.__typename}</div>
                        {msg.parts && msg.parts.map((part: any, j: number) => (
                            <div key={j} className="mb-2">
                                {/* Message text content */}
                                {part.content && !part.tool_name && (
                                    <div className="pl-2 text-black whitespace-pre-wrap">{part.content}</div>
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
                                            {part.content}
                                        </div>
                                        <div className="text-xs text-gray-500">ID: {part.tool_call_id}</div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                ))}
            </div>
            <Link className="block mt-4 text-gray-600 underline" href={`/state/${params.state_file}`}>Back to agency state</Link>
        </main>
    );
}
