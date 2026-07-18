# Alejandro Brito

**Desarrollador full-stack e integrador de IA** — Ciudad de Panamá

Construyo piezas concretas que mueven una métrica concreta: SaaS, ERPs, CRMs
y agentes de IA para fundadores y empresas que valoran el detalle.
Sin maquetas, sin demos: software en producción.

**[alejandrobrito.dev](https://alejandrobrito.dev)** · [alejandrobritoolivera@gmail.com](mailto:alejandrobritoolivera@gmail.com)

---

### Productos

| Proyecto | Qué es | Stack |
|---|---|---|
| **[Morph](https://github.com/AleBrito124356/morph)** | Migraciones de bases de datos asistidas por IA: análisis, cotización fija y artefactos listos para ejecutar. [En vivo →](https://morph-zeta.vercel.app) | Next.js 15 · Prisma · Stripe · Claude |
| **Norden** · privado | Administración de propiedades (PH) con copiloto de IA, para el mercado panameño. Backend FastAPI: 124 endpoints, 71 tests. | Next.js · FastAPI · PostgreSQL |
| **SIMANLLA** · privado | ERP de mantenimiento y llamadas para Elevadores Goldstar. | — |
| **Card Control** · privado | Control de tarjetas corporativas para Castro & Castro. | Next.js · MySQL |

---

### 🤖 Open source — Agentes de IA y herramientas

Una colección de **32 repos** de código terminado: agentes de IA de todo tipo,
RAG, fine-tuning, automatización con n8n, servidores MCP, plantillas y utilidades.
Todo está listo para ejecutarse y **funciona con la [API gratuita de NVIDIA NIM](https://build.nvidia.com)**
(endpoint compatible con OpenAI). Las claves en los repos son *placeholders* —
cada README explica en 2 minutos de dónde sacar la tuya, gratis.

Cada repo trae README con diagramas, licencia MIT, `.env.example` y código sin stubs.

#### Agentes de IA — patrones y frameworks

| Repo | Qué contiene |
|---|---|
| [nim-agent-lab](https://github.com/AleBrito124356/nim-agent-lab) | 12 patrones de agente en Python puro: ReAct, planner-executor, reflection, routing, memoria, guardrails, code-interpreter, orquestador |
| [langgraph-agent-flows](https://github.com/AleBrito124356/langgraph-agent-flows) | 8 topologías LangGraph: equipos supervisor, bucles de reflexión, human-in-the-loop, memoria persistente, fan-out paralelo |
| [crewai-team-templates](https://github.com/AleBrito124356/crewai-team-templates) | 5 *crews* CrewAI listas: equipo de contenido, market research, documentación de código, auditoría SEO, lanzamiento de producto |
| [agent-memory-systems](https://github.com/AleBrito124356/agent-memory-systems) | 5 arquitecturas de memoria para agentes (ventana, resumen, episódica vectorial, hechos, grafo) con benchmark de recall |
| [agent-tools-library](https://github.com/AleBrito124356/agent-tools-library) | Librería de 25+ herramientas para agentes (web, archivos, datos, mates, texto) con schemas OpenAI y tests |
| [durable-agents](https://github.com/AleBrito124356/durable-agents) | Patrones de producción para agentes de larga duración: cola SQLite, checkpointing, reanudación tras crash, gates de aprobación |
| [agent-security-toolkit](https://github.com/AleBrito124356/agent-security-toolkit) | Pruebas de seguridad para *tus* agentes: corpus de prompt-injection, runner con juez, y agente endurecido de referencia |

#### Agentes aplicados — hacen un trabajo concreto

| Repo | Qué hace |
|---|---|
| [deep-research-agent](https://github.com/AleBrito124356/deep-research-agent) | Agente de investigación autónomo: planifica, busca, lee fuentes, contrasta afirmaciones y escribe un informe con citas |
| [code-review-agent](https://github.com/AleBrito124356/code-review-agent) | Revisión automática de PRs de GitHub y diffs locales, con severidad, confianza y control de ruido; Action incluida |
| [text-to-sql-agent](https://github.com/AleBrito124356/text-to-sql-agent) | Lenguaje natural → SQL con introspección de esquema, guardas *SELECT-only* y reintentos auto-correctivos |
| [support-agent-stack](https://github.com/AleBrito124356/support-agent-stack) | Agente de soporte completo: backend FastAPI con RAG, enrutamiento por intención, escalado a tickets y widget de chat |
| [inbox-agent](https://github.com/AleBrito124356/inbox-agent) | Triaje de correo por IMAP: clasifica, extrae tareas y redacta borradores en tu voz. Solo borradores, nunca envía |
| [telegram-ai-agents](https://github.com/AleBrito124356/telegram-ai-agents) | 3 bots de Telegram: asistente con herramientas y memoria, RAG sobre tus PDFs, y bot de visión |
| [playwright-web-agents](https://github.com/AleBrito124356/playwright-web-agents) | Agentes de navegador con Playwright: scraping dirigido, llenado de formularios, monitoreo y research multi-página |
| [voice-agent-starter](https://github.com/AleBrito124356/voice-agent-starter) | Asistente de voz local: faster-whisper + LLM en NIM + edge-tts, con push-to-talk y respuestas en streaming |

#### RAG, fine-tuning y evaluación

| Repo | Qué contiene |
|---|---|
| [rag-blueprints](https://github.com/AleBrito124356/rag-blueprints) | 8 arquitecturas RAG de básica a agéntica: híbrida BM25+denso, reranking, HyDE, parent-document, evaluación |
| [fine-tuning-playbook](https://github.com/AleBrito124356/fine-tuning-playbook) | Fine-tuning de LLMs de punta a punta: datos, QLoRA SFT, DPO, evaluación y export a GGUF, con tablas de VRAM |
| [llm-eval-toolkit](https://github.com/AleBrito124356/llm-eval-toolkit) | Testing de prompts y evaluación de LLMs: suites YAML, LLM-como-juez, A/B pareado, métricas RAG, reportes HTML |
| [structured-extraction-agents](https://github.com/AleBrito124356/structured-extraction-agents) | Documentos desordenados → JSON validado (facturas, CVs, contratos) con Pydantic y bucle de auto-reparación |
| [mcp-server-cookbook](https://github.com/AleBrito124356/mcp-server-cookbook) | 5 servidores Model Context Protocol listos (SQL, web, knowledge base, filesystem, REST) con configs para Claude |
| [nim-free-api-quickstarts](https://github.com/AleBrito124356/nim-free-api-quickstarts) | Quickstarts mínimos de cada capacidad de NIM: chat, streaming, visión, embeddings, function calling — Python, JS y curl |

#### Automatización e infraestructura

| Repo | Qué contiene |
|---|---|
| [n8n-ai-workflows](https://github.com/AleBrito124356/n8n-ai-workflows) | 12 workflows n8n importables: asistente de Telegram, chatbot RAG, triaje de email, extracción de facturas, agente SQL |
| [python-automation-toolbox](https://github.com/AleBrito124356/python-automation-toolbox) | 20 scripts de automatización para la vida real: organizar archivos, dedupe, imágenes, PDFs, backups, QR, uptime, TTS |
| [docker-compose-stacks](https://github.com/AleBrito124356/docker-compose-stacks) | Stacks Docker Compose copia-y-pega: bases de datos, colas, monitoreo, n8n, Ollama, reverse proxy — con healthchecks |
| [ml-deployment-patterns](https://github.com/AleBrito124356/ml-deployment-patterns) | De `joblib` a producción: servir sklearn/ONNX con FastAPI, validación, versionado, detección de drift y load testing |

#### Plantillas, starters y utilidades

| Repo | Qué contiene |
|---|---|
| [fastapi-production-template](https://github.com/AleBrito124356/fastapi-production-template) | Starter FastAPI serio: SQLAlchemy async + Alembic, JWT con rotación, Redis, rate limiting, tests, Docker y CI |
| [nextjs-ai-chat-template](https://github.com/AleBrito124356/nextjs-ai-chat-template) | Chat de IA en Next.js 15 con streaming (Vercel AI SDK → NIM), historial, markdown, model picker; estética clara y limpia |
| [tailwind-landing-sections](https://github.com/AleBrito124356/tailwind-landing-sections) | 15 secciones de landing en Tailwind (heroes, pricing, FAQ, navbars) con estética zinc+azul; cero build para previsualizar |
| [remotion-video-templates](https://github.com/AleBrito124356/remotion-video-templates) | 6 plantillas de video programático en Remotion: intro de logo, lower thirds, tipografía cinética, charts, promo |
| [blender-python-toolkit](https://github.com/AleBrito124356/blender-python-toolkit) | Automatización headless de Blender: escenas procedurales, turntables de producto, render por lotes, charts 3D |
| [pdf-power-tools](https://github.com/AleBrito124356/pdf-power-tools) | Un CLI para todo lo de PDF: unir, dividir, comprimir, marca de agua, cifrar, extraer texto/tablas/imágenes, OCR |
| [recetas-ia](https://github.com/AleBrito124356/recetas-ia) 🇪🇸 | 15 recetas de IA **en español**: resumir PDFs, clasificar gastos, transcribir audio, responder reseñas — para la comunidad hispana |

---

### Stack

**Web** — TypeScript · React · Next.js · Tailwind · Three.js
**Backend** — Python (FastAPI, Flask) · Node · PostgreSQL (Neon, Supabase) · MySQL · Prisma
**IA** — Claude & OpenAI APIs · NVIDIA NIM · LangGraph · CrewAI · RAG · fine-tuning · copilotos y agentes en producción
**Además** — n8n · MCP · Remotion · Blender scripting · Docker · Cloudflare · Vercel

---

¿Un problema que resolver con software o IA? **[Hablemos →](https://alejandrobrito.dev/#contact)**
