# LangGraph streaming and `LangchainCallbackHandler`

This note documents the block in [app.py](app.py) that streams the graph and attaches Chainlit’s LangChain callbacks.

## Code (excerpt)

```48:58:app.py
    callback = cl.LangchainCallbackHandler()
    summary = ""

    try:
        async for chunk in graph.astream(
            {"company": company},
            config={"callbacks": [callback]},
        ):
            data = chunk.get("analyze") if isinstance(chunk, dict) else None
            if isinstance(data, dict) and data.get("summary"):
                summary = data["summary"]
```

## What each part does

1. **`LangchainCallbackHandler()`**  
   Chainlit’s adapter for LangChain run events. Passed in `config={"callbacks": [callback]}`, it lets Chainlit show LangChain/LangGraph activity in the UI where supported (e.g. collapsible steps for model or tool calls during that run).

2. **`summary = ""`**  
   Accumulator for the markdown string you will send to the user after streaming finishes.

3. **`graph.astream({...}, config=...)`**  
   Runs the compiled LangGraph **asynchronously** and yields **updates** as nodes complete. Each `chunk` is typically a dict whose keys are **LangGraph node names** and whose values are partial state updates from that node.

4. **`{"company": company}`**  
   Initial state: the company phrase the user typed.

5. **`chunk.get("analyze")`**  
   This project’s graph defines a node named `analyze` (see [main/src/trader/graph.py](main/src/trader/graph.py)). Stream events for that node appear under the `"analyze"` key.

6. **`data.get("summary")`**  
   The `analyze` node returns a state patch that includes `summary` (the final prose for the chat). The loop overwrites `summary` whenever a new value appears; usually the **last** value is the complete response.

## Why stream instead of `invoke`?

Streaming keeps the Chainlit integration aligned with incremental graph execution and can surface progress via callbacks. Even if you only read `summary` at the end, `astream` matches an async Chainlit handler.

## If you rename or split graph nodes

Update `chunk.get("analyze")` to match the new node name, or merge fields from multiple keys if several nodes contribute to the reply.
