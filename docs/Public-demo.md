# Public demo

The user authorized a free public demo on 31 October 2026, replacing the earlier localhost-only preference for this demo only.

This is a temporary Cloudflare Quick Tunnel to a separate Streamlit process on loopback port 8502. It is not an always-on cloud deployment: the host computer, Ollama, Streamlit and the tunnel must remain running, and the computer must stay awake and online. Restarting the tunnel creates a different URL. The recorded video and public GitHub repository remain the durable submission artifacts.

Run the separate application process with `DECISIONDESK_PUBLIC_DEMO=1` and `python -m streamlit run app.py --server.address=127.0.0.1 --server.port=8502`. Set `--browser.serverAddress` to the tunnel hostname. The ordinary local launcher continues to use port 8501 without this environment variable.

Public mode gives each Streamlit browser session a random, server-generated workspace directory beneath ignored `data/public-demo/`. It never loads the owner's workspace. New sessions contain clearly labelled fictional examples initialized with offline rules; those fixtures are not evidence of AI generation or human approval. Live AI uses the existing host-local Ollama model, Qwen3 1.7B. Public inputs must be fictional; do not upload private meetings. Data is temporary and a refreshed/disconnected session may lose access to its previous workspace. Export notes/backups before leaving.

GitHub connection checks and issue publishing are blocked at the integration boundary in public mode, and posting controls are omitted. The demo does not expose Ollama's HTTP port or a shell. No API keys, paid services, new accounts or production data are included.

Cloudflare Quick Tunnels are intended for testing and development, with no availability guarantee: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
