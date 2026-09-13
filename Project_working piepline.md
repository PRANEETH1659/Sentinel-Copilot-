🐳 Docker
Just a box that runs Elasticsearch on your machine without messing up your Windows setup. Like renting a small room just for the library's filing cabinets, so they don't clutter your house. You don't interact with Docker directly once it's running — it just quietly keeps Elasticsearch alive in the background.

🔍 Elasticsearch
This is the library's filing cabinet + index card system. When you ran ingest_ph1.py, your 3 documents got chopped into 11 chunks (like tearing a book into paragraphs) and stored here. It can search two ways:

Keyword search (BM25) — like searching "which pages contain the word ransomware"
Vector/kNN search — searching by meaning, even if the exact word isn't there

🧠 Embeddings (nomic-embed-text via Ollama)
This turns text into a list of numbers (a "vector") that captures its meaning. Example: "malware attack" and "virus infected the system" would get similar numbers, even though the words are different. It's like giving every paragraph a GPS coordinate on a "meaning map" — sentences with similar meaning land near each other.

🦙 Ollama
This is your local AI engine — it runs two different models for two different jobs:

nomic-embed-text → creates those meaning-vectors above
qwen2.5:7b (was llama3.2 until the compound-tool-call fix below) → the one that actually writes the answer in plain English once it has the right document chunks in front of it

Putting it together — what happens when you hit /ask:

Your question also gets turned into a vector (via Ollama's embedding model)
Elasticsearch compares that vector + keywords against your 11 stored chunks, finds the most relevant ones
Those chunks get stuffed into a prompt like: "Using this info, answer this question..."
Ollama's chat model (qwen2.5:7b) reads that and writes the final answer

So really: Elasticsearch = memory, Ollama = brain (both for understanding and answering), Docker = the box that houses the memory, Embeddings = the translator that turns words into a "meaning" a computer can compare.


LangGraph : A framework for building AI workflows where the AI itself picks which tool to use ,instead of you hardcoding one fixed path 

Langgraph remembers the States .

Langgraph carries along everything that's happend so far- your original question, what was searched,what was found, what failed. 

It understands meaning not just key word matching 

LangGraph has 3 things: Node, Edges, State

Node = actual workers/ steps 

in our example they are going to be 1.decide_tool, 2.search_knowledge_base,3.search_logs,4.generate_answer

Edges=the arrows connecting nodes

"decides after finishing this task where shoudl i go next "

2 -types of edges:
1.Normal edeg-fixed , always goes the same way . ex:"After search_logs always to the generate_ansewr"

2.Conditional edge:
This is the smart one.It looks at what just happend and decides which node to go next. This is literally where your "receptionist deciding which department"

---

UPDATE (written after the code was actually built, so these notes match
app/agent_ph2.py):

The 4-node list above was the plan. What got built is simpler - TWO nodes:

  think - decide_tool and generate_answer rolled into one node. Each time
          the model runs it either asks for a tool, or writes the final
          answer. Same node does both jobs.

  act   - LangGraph's prebuilt ToolNode. It runs whichever tool the model
          just asked for, so search_knowledge_base and search_logs both sit
          behind this ONE node, instead of being a node each.

Which makes the edges:
  - Conditional edge out of think: asked for a tool -> act, otherwise -> END
  - Normal edge out of act: always straight back to think

So the receptionist is `think`. It decides the department, `act` does the
work, and it always comes back to reception - looping until there is
nothing left to route, which is when the final answer comes out.

---

Phase 3 (written after the code was actually built, same as the LangGraph
update above):

🗄️ Redis
A sticky-note memory, separate from Elasticsearch. Elasticsearch is the
filing cabinet with ALL the documents; Redis just remembers "I already
answered this exact question, here's what I said" so the second time
around we skip searching the filing cabinet and skip asking Ollama
entirely - just hand back the sticky note. Measured: ~71s down to 0.26s on
a repeat question.

The sticky note is labeled with the question AND which model answered it
(`CHAT_MODEL`), not just the question - otherwise switching models later
(like we did, llama3.2 -> qwen2.5:7b) could hand back an old answer
written by a model we don't even use anymore.

⏱️ Tracing (app/tracing_ph3.py)
Just a stopwatch, nothing fancier. Every request gets its own `Trace`
object (never shared between requests, so two people asking questions at
the same time can't mix up each other's timings) that records how long
each step took - `hybrid_search_ms`, `llm_generate_ms` - and that gets
handed back in the response. Didn't reach for OpenTelemetry/Jaeger here;
this is one Python process, not a fleet of microservices, so a plain
dict of step-name -> milliseconds answers "where did the time go" just
as well.

📡 Streaming (`/ask/stream`, `/ask-agent/stream`)
Instead of Ollama handing back the whole answer in one go, `stream: True`
makes it hand back one word (technically one "token") at a time, and we
forward each one to whoever's asking as it arrives - Server-Sent Events,
which is just plain HTTP with `data: ...` lines instead of one JSON blob.
Doesn't make the AI actually faster, just makes the wait feel shorter
since you watch it type instead of staring at nothing.

The agent version of this was the fiddly part: LangGraph's
`stream_mode="messages"` streams tokens from EVERY model call in the
graph, including the one that's just deciding which tool to use (that one
has no real text, just an empty string + a tool-call). Checked this by
hand before writing the real code: tool-call turns show up as empty-
content chunks, and only the actual final-answer turn has real text - so
we just skip forwarding anything with empty content, and the caller only
ever sees real words.
