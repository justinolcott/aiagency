import json
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.lines import Line2D
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as mpimg
import textwrap
import re
import os
import requests # For fetching SVG
import io       # For handling byte streams
import cairosvg # For converting SVG to PNG (requires installation: pip install cairosvg)

# --- Configuration ---
file_path = '/Users/justinolcott/Documents/Code/potterywheel/aiagency/conversations/tariff_meeting_5.json' # Assumes the JSON data is saved here
output_filename = 'figures/conversation_animation_robot_nodes.gif'
local_png_filename = 'robot.png' # Temporary file for rasterized image

# Text and Node Sizes/Appearance
# Note: node_size is less relevant now, image size is controlled by image_zoom
image_zoom = 0.10         # Controls the size of the robot image (adjust as needed)
label_y_offset = 0.05     # Fine-tune vertical position of agent name relative to image center
title_font_size = 18
legend_font_size = 11
label_font_size = 11
text_box_font_size = 13
bg_circle_scale = 1.4     # How much larger the background highlight circle is than the image base size

# Other Config
text_wrap_width = 70
message_char_limit = 250
animation_interval = 2000
animation_fps = 1000 / animation_interval
layout_k = 4.0            # Increased spread more for larger image nodes

# --- Setup: Fetch and Convert SVG ---
use_image_nodes = False
robot_img_data = None

robot_img_data = mpimg.imread(local_png_filename)
use_image_nodes = True
print("PNG image loaded for animation.")
# --- Load Data ---
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print("Data loaded successfully.")
except FileNotFoundError:
    print(f"Error: File not found at {file_path}. Please ensure the file exists.")
    exit()
except json.JSONDecodeError as e:
    print(f"Error: Could not decode JSON from {file_path}. Details: {e}")
    exit()
except Exception as e: print(f"An unexpected error occurred during file loading: {e}"); exit()

# --- 1. Extract Agent Information (Same as before) ---
agents_info = {}
main_agent_data = next((agent for agent in data['agents'] if agent['id'] == '0'), None)
if main_agent_data: agents_info[main_agent_data['id']] = {'name': main_agent_data['name']}
main_agent_name = agents_info.get('0', {}).get('name', 'Unknown_Main_Agent')
all_potential_agent_names = {main_agent_name}
if main_agent_data:
    for msg in main_agent_data.get('message_history', []):
         if msg['kind'] == 'response' and any(part.get('tool_name') == 'create_new_agent' for part in msg['parts']):
             for part in msg['parts']:
                 if part.get('part_kind') == 'tool-call' and part.get('tool_name') == 'create_new_agent':
                     try: all_potential_agent_names.add(json.loads(part['args']).get('name', 'Unnamed Agent'))
                     except: pass

# --- 2. Extract Chronological Steps (Same as before) ---
conversation_steps = []
agent_tool_calls = {}
created_agent_ids = {'0'}
meeting_turn_regex = re.compile(r'^\[(.*?)\s*(?:\[Active Host\])?\s*\(\s*(\d+(?:_temp)?)\s*\)\]:\s*(.*)', re.IGNORECASE)

# Add main agent start step
if main_agent_name != 'Unknown_Main_Agent' and main_agent_data:
     first_timestamp = "START"
     if main_agent_data.get('message_history') and main_agent_data['message_history'][0].get('parts'):
         first_timestamp = main_agent_data['message_history'][0]['parts'][0].get('timestamp', "START")
     conversation_steps.append({'type': 'creation_complete', 'agent_name': main_agent_name, 'agent_id': '0', 'content': f"{main_agent_name} initialized.", 'timestamp': first_timestamp, 'tool_call_id': None, 'speaker': None})

# Process main_agent's history (simplified loop content for brevity, logic unchanged)
main_agent_history = main_agent_data.get('message_history', []) if main_agent_data else []
for msg_index, msg in enumerate(main_agent_history):
    message_base_timestamp = msg.get('timestamp', f"MSG_{msg_index:04d}")
    # A. Agent Creation Requests
    if msg['kind'] == 'response' and any(part.get('tool_name') == 'create_new_agent' for part in msg['parts']):
        for part_index, part in enumerate(msg['parts']):
            if part.get('part_kind') == 'tool-call' and part.get('tool_name') == 'create_new_agent':
                 try:
                     args=json.loads(part['args']); agent_being_created=args.get('name', 'UA'); tool_call_id=part.get('tool_call_id')
                     step_timestamp=part.get('timestamp',f"{message_base_timestamp}_p{part_index}")
                     if tool_call_id: agent_tool_calls[tool_call_id] = {'agent_name': agent_being_created,'request_timestamp':step_timestamp}
                 except: pass
    # B. Agent Creation Confirmations
    elif msg['kind'] == 'request' and any(part.get('tool_name') == 'create_new_agent' for part in msg['parts']):
         for part_index, part in enumerate(msg['parts']):
             if part.get('part_kind') == 'tool-return' and part.get('tool_name') == 'create_new_agent':
                 tool_call_id = part.get('tool_call_id'); step_timestamp=part.get('timestamp',f"{message_base_timestamp}_p{part_index}")
                 original_call = agent_tool_calls.get(tool_call_id); agent_name=original_call['agent_name'] if original_call else f"A_{tool_call_id}"
                 agent_id_match = re.search(r'ID:\s*(\d+)', part.get('content','')); agent_id=agent_id_match.group(1) if agent_id_match else None
                 if agent_id: created_agent_ids.add(agent_id); agents_info.setdefault(agent_id, {'name': agent_name}); all_potential_agent_names.add(agent_name)
                 conversation_steps.append({'type':'creation_complete','agent_name':agent_name,'agent_id':agent_id,'content':f"{agent_name} created.",'timestamp':step_timestamp,'tool_call_id':tool_call_id,'speaker':None})
    # C. Meeting Call Request
    elif msg['kind'] == 'response' and any(part.get('tool_name') == 'call_meeting' for part in msg['parts']):
        for part_index, part in enumerate(msg['parts']):
            if part.get('part_kind') == 'tool-call' and part.get('tool_name') == 'call_meeting':
                 tool_call_id=part.get('tool_call_id'); step_timestamp=part.get('timestamp',f"{message_base_timestamp}_p{part_index}")
                 try: objective=json.loads(part['args']).get('meeting_objective','Discuss topic.')
                 except: objective='Discuss topic.'
                 conversation_steps.append({'type':'meeting_start','content':f"Meeting Called: {objective}",'timestamp':step_timestamp,'tool_call_id':tool_call_id,'speaker':None,'agent_name':None,'agent_id':None})
                 agent_tool_calls[tool_call_id] = {'type':'meeting','start_timestamp':step_timestamp}
    # D. Meeting Call Return
    elif msg['kind'] == 'request' and any(part.get('tool_name') == 'call_meeting' for part in msg['parts']):
         for part_index, part in enumerate(msg['parts']):
             if part.get('part_kind') == 'tool-return' and part.get('tool_name') == 'call_meeting':
                 tool_call_id=part.get('tool_call_id'); meeting_end_ts=part.get('timestamp',f"{message_base_timestamp}_p{part_index}")
                 raw_meeting_content=part.get('content',''); original_call=agent_tool_calls.get(tool_call_id)
                 meeting_start_ts=original_call['start_timestamp'] if original_call else meeting_end_ts
                 meeting_turns=[]; turn_counter=0; lines=raw_meeting_content.splitlines()
                 for line in lines:
                     match=meeting_turn_regex.match(line.strip())
                     if match:
                         s_name_raw,s_id_raw,m_content_raw = match.groups(); s_id=s_id_raw.strip().replace('_temp',''); s_name=agents_info.get(s_id,{}).get('name',s_name_raw.strip()); all_potential_agent_names.add(s_name)
                         m_content = m_content_raw.replace('READY_TO_MOVE_ON','').replace('READY_TO_END_MEETING','').strip()
                         if m_content: turn_counter+=1; turn_timestamp=f"{meeting_start_ts}_turn_{turn_counter:04d}"; meeting_turns.append({'type':'meeting_turn','speaker':s_name,'agent_id':s_id,'content':m_content,'timestamp':turn_timestamp,'tool_call_id':tool_call_id})
                 conversation_steps.extend(meeting_turns)
                 conversation_steps.append({'type':'meeting_end','content':"Meeting Concluded.",'timestamp':meeting_end_ts,'speaker':None,'agent_name':None,'agent_id':None,'tool_call_id':tool_call_id})
    # F. Final Summary Text
    elif msg['kind'] == 'response' and any(part.get('part_kind') == 'text' for part in msg['parts']):
         for part_index, part in enumerate(msg['parts']):
             if part.get('part_kind') == 'text':
                 step_timestamp=part.get('timestamp',f"{message_base_timestamp}_p{part_index}"); content=part.get('content','').strip()
                 if content: conversation_steps.append({'type':'summary','speaker':main_agent_name,'agent_id':'0','receiver':None,'content':content,'timestamp':step_timestamp,'tool_call_id':None})

# Sort steps
conversation_steps.sort(key=lambda x: x.get('timestamp', ''))

# --- 3. Setup Graph Layout ---
G = nx.Graph()
all_potential_agent_names_filtered = {name for name in all_potential_agent_names if name}
temp_G_layout = nx.Graph()
temp_G_layout.add_nodes_from(all_potential_agent_names_filtered)
pos = nx.spring_layout(temp_G_layout, seed=42, k=layout_k) # Use configured k

# --- 4. Set up Animation ---
fig, ax = plt.subplots(figsize=(20, 16))
plt.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
plt.close()

# Define colors and styles
node_color_default = 'lightblue'
node_color_active = 'yellow'
edge_color_main_link = '#cccccc'
edge_width_main_link = 1.5
text_display_props = dict(boxstyle='round,pad=0.5', fc='wheat', alpha=0.75)

# Determine image extent for background circle scaling (approximate)
# Based on zoom and image aspect ratio (assuming roughly square for calculation)
# This is heuristic and may need adjustment.
img_display_radius_approx = image_zoom * 5 # Trial and error scaling factor

def update(frame_num):
    ax.cla()
    ax.axis('off')
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    current_step = conversation_steps[frame_num]
    step_type = current_step['type']
    content = current_step.get('content', '')
    speaker = current_step.get('speaker')
    created_agent = current_step.get('agent_name')

    if len(content) > message_char_limit: content = content[:message_char_limit] + "..."

    # Track active agents
    active_agents_in_frame_names = set()
    for i in range(frame_num + 1):
        step = conversation_steps[i]
        if step['type'] == 'creation_complete' and step.get('agent_name'):
            active_agents_in_frame_names.add(step['agent_name'])

    # Build graph for current frame
    G.clear()
    if active_agents_in_frame_names:
        G.add_nodes_from(active_agents_in_frame_names)
        if main_agent_name not in G.nodes() and main_agent_name in all_potential_agent_names_filtered:
            G.add_node(main_agent_name)

    current_pos = {node: pos[node] for node in G.nodes() if node in pos}

    # Determine focus node
    current_focus_node_name = None
    if step_type == 'creation_complete': current_focus_node_name = created_agent
    elif step_type in ['meeting_turn', 'summary']: current_focus_node_name = speaker

    # Draw EDGES
    main_agent_edges = []
    if main_agent_name in G.nodes():
        main_agent_edges = [(main_agent_name, other_node) for other_node in G.nodes() if other_node != main_agent_name]
    if main_agent_edges and G.nodes():
        valid_edges = [edge for edge in main_agent_edges if edge[0] in current_pos and edge[1] in current_pos]
        if valid_edges:
            nx.draw_networkx_edges(G, current_pos, ax=ax, edgelist=valid_edges,
                                   edge_color=edge_color_main_link, width=edge_width_main_link, alpha=0.8) # zorder=0 (behind nodes)

    # Draw NODES (Images or Fallback)
    if use_image_nodes and G.nodes():
        for node_name, (x, y) in current_pos.items():
            is_focus = (node_name == current_focus_node_name)
            node_color = node_color_active if is_focus else node_color_default

            # Draw background circle for color indication
            # bg_radius = img_display_radius_approx * bg_circle_scale # Scale based on image size estimate
            # bg_circle = plt.Circle((x, y), radius=bg_radius, color=node_color, alpha=0.) # zorder=1 (behind image)
            # ax.add_patch(bg_circle)
            bg_radius = img_display_radius_approx * bg_circle_scale
            if is_focus:
                bg_circle = plt.Circle((x, y), radius=bg_radius, color=node_color_default, alpha=0.6)  # Brighter circle
            else:
                bg_circle = plt.Circle((x, y), radius=bg_radius, color=node_color_default, alpha=0.0)  # Subtle circle
            ax.add_patch(bg_circle)

            # Draw image node
            im_offset = OffsetImage(robot_img_data, zoom=image_zoom, alpha=1.0)
            ab = AnnotationBbox(im_offset, (x, y), xycoords='data', frameon=False, pad=0) # zorder=2 (above circle)
            ax.add_artist(ab)

            # Draw label above image (adjust offset based on data coords)
            ax.text(x, y + label_y_offset, node_name,
                    ha='center', va='bottom', fontsize=label_font_size, fontweight='bold', # zorder=3 (topmost)
                    bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.5)) # Slight background for label readability
    elif G.nodes(): # Fallback to standard nodes if image loading failed
        node_colors = [node_color_active if node == current_focus_node_name else node_color_default for node in G.nodes()]
        nx.draw_networkx_nodes(G, current_pos, ax=ax, node_color=node_colors, node_size=3000, alpha=0.9) # Use a fallback size
        nx.draw_networkx_labels(G, current_pos, ax=ax, font_size=label_font_size, font_weight='bold')


    # Update Title
    title = f"Step {frame_num + 1}/{len(conversation_steps)}: {step_type.replace('_', ' ').title()}"
    if speaker: title += f" - Speaker: {speaker}"
    elif created_agent: title += f" - Agent: {created_agent}"
    ax.set_title(title, fontsize=title_font_size, wrap=True)

    # Update Text Box
    wrapped_content = textwrap.fill(content, width=text_wrap_width)
    ax.text(0.5, 0.5, wrapped_content, ha='center', va='center', fontsize=text_box_font_size,
            wrap=True, transform=ax.transAxes, bbox=text_display_props)

    # Redraw Legend
    legend_elements = [
        # Use simple markers for legend, label appropriately
        Line2D([0], [0], marker='o', color='w', label='Agent', markerfacecolor=node_color_default, markersize=12),
        Line2D([0], [0], marker='o', color='w', label='Focus/Speaker', markerfacecolor=node_color_active, markersize=12),
        Line2D([0], [0], color=edge_color_main_link, lw=edge_width_main_link, label='Link to Main Agent'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=legend_font_size)

    # Adjust plot limits
    ax.relim()
    ax.autoscale_view(tight=False)
    ax.margins(0.2) # Increased margin further for images

    return []

# --- 5. Create and Save Animation ---
print(f"Processing {len(conversation_steps)} steps for animation...")
ani = animation.FuncAnimation(fig, update, frames=len(conversation_steps),
                              interval=animation_interval, repeat=False, blit=False)

# Save the animation as a GIF
print(f"\nAttempting to save animation to {output_filename}...")
try:
    ani.save(output_filename, writer='pillow', fps=animation_fps, dpi=100)
    print(f"Animation successfully saved as {output_filename}")
except Exception as e:
     print(f"\nError saving animation: {e}")
     print("Ensure 'pillow' is installed: pip install pillow")
     print("If issues persist, ensure matplotlib dependencies (ffmpeg/ImageMagick) are available.")

# Optional: Display in Jupyter
# from IPython.display import HTML
# HTML(ani.to_jshtml())
