# ICT 2022 Setup Engine

Agente MCP + Indicador Pine Script que detecta setups de alta probabilidad basados en el **Modelo ICT 2022** (Inner Circle Trader) para **NQ, ES y YM**.

Claude analiza el mercado en tiempo real siguiendo el flujo multi-timeframe:

```
1H (bias + FVG) → 15m (sweep) → 2m (CISD + OB → entry)
```

---

## Qué incluye

| Componente | Descripción |
|------------|-------------|
| **Indicador Pine Script** | Detecta HTF bias, sweeps, impulsos, Order Blocks y genera señales de entrada en TradingView |
| **MCP Server (Python)** | 12 tools para análisis ICT en tiempo real — Claude ejecuta el flujo completo |
| **Webhook Receiver** | Recibe alertas JSON de TradingView para señales en vivo |
| **Agente ICT** | Instrucciones para que Claude actúe como trader institucional |

---

## Requisitos

- **Python 3.11+**
- **uv** (package manager)
- **VS Code** con GitHub Copilot (Chat)
- **TradingView** (cualquier plan — web, desktop o móvil)
- **ngrok** (gratis) para recibir webhooks de TradingView

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/ict-2022-setup-engine.git
cd ict-2022-setup-engine
```

### 2. Instalar uv (si no lo tienes)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Instalar dependencias del MCP server

```bash
cd mcp-ict-agent
uv sync
```

### 4. Verificar que funciona

```bash
uv run python -c "from ict_mcp.server import mcp; print('✓ Server OK')"
```

---

## Configurar VS Code

### 1. Abrir el proyecto en VS Code

```bash
code .
```

### 2. El MCP se configura automáticamente

El archivo `.vscode/mcp.json` ya está incluido. VS Code detectará el server al abrir el proyecto.

Si necesitas verificar, el archivo contiene:

```json
{
  "servers": {
    "ict-agent": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "${workspaceFolder}/mcp-ict-agent", "run", "ict-mcp-server"]
    }
  }
}
```

### 3. Reiniciar VS Code

Cierra y abre VS Code para que cargue el MCP server.

---

## Usar el Agente ICT

En el chat de GitHub Copilot, invoca el agente:

```
@ict-mcp-agent analiza NQ
```

Claude ejecutará el flujo completo:
1. Verifica macro window y estado del mercado
2. Analiza bias HTF en 1H (FVGs activos)
3. Detecta sweeps de liquidez en 15m
4. Busca displacement + CISD + Order Blocks en 2m
5. Califica el setup (A+/A/B/C)
6. Si el rating es ≥ B, muestra Entry, SL, TP

### Comandos disponibles

| Comando | Qué hace |
|---------|----------|
| `@ict-mcp-agent analiza NQ` | Análisis completo multi-TF |
| `@ict-mcp-agent analiza ES` | Lo mismo para S&P 500 |
| `@ict-mcp-agent ¿hay señal en NQ?` | Consulta última señal de TradingView |
| `@ict-mcp-agent estado del webhook` | Verifica conexión con TradingView |
| `@ict-mcp-agent detecta FVG en NQ 1h` | Solo detección de FVG |
| `@ict-mcp-agent liquidez en ES 15m` | Solo swing points y sweeps |

---

## Conectar con TradingView (Webhooks)

### 1. Agregar el indicador a TradingView

1. Abre TradingView → Pine Editor (pestaña inferior)
2. Click "Open" → "New blank indicator"
3. Borra el contenido y pega todo el archivo `src/ICT_2022_Setup_Engine.pine`
4. Click **"Add to chart"**
5. El indicador aparecerá con un panel ICT en la esquina superior derecha

### 2. Exponer el webhook con ngrok

```bash
# Instalar ngrok (una sola vez)
brew install ngrok
# o en Linux: snap install ngrok

# Exponer el puerto del MCP
ngrok http 8642
```

Copia la URL HTTPS que aparece (ej: `https://abc123.ngrok-free.app`)

### 3. Crear alertas en TradingView

En TradingView:

1. Click en el ícono de reloj (Alerts) → **"Create Alert"**
2. **Condition**: selecciona "ICT 2022 — Flow X | HTF Persistent Bias"
3. Selecciona una de las alertas:
   - `ICT LONG — En OB`
   - `ICT SHORT — En OB`
   - `ICT Bear Impulso`
   - `ICT Bull Impulso`
4. En **Notifications** → activa **"Webhook URL"**
5. Pega la URL de ngrok
6. Click **"Create"**

> Repite para cada tipo de alerta (4 en total).

### 4. Verificar conexión

```
@ict-mcp-agent estado del webhook
```

---

## Estructura del Proyecto

```
ict-2022-setup-engine/
├── README.md                          ← Este archivo
├── src/
│   └── ICT_2022_Setup_Engine.pine     ← Indicador Pine Script v6
├── mcp-ict-agent/
│   ├── pyproject.toml                 ← Dependencias Python
│   └── src/ict_mcp/
│       ├── server.py                  ← MCP server (12 tools)
│       ├── data_provider.py           ← Datos OHLCV via yfinance
│       ├── ict_analysis.py            ← Motor de análisis ICT
│       └── webhook.py                 ← Receptor de webhooks
├── .vscode/
│   └── mcp.json                       ← Config MCP para VS Code
├── .github/
│   └── agents/
│       └── ict-mcp-agent.agent.md     ← Instrucciones del agente
├── docs/
│   ├── TRADINGVIEW_SETUP.md           ← Guía detallada TradingView
│   └── ARCHITECTURE.md                ← Arquitectura técnica
└── scripts/
    └── validate-pine.sh               ← Linter para Pine Script
```

---

## MCP Tools disponibles

| Tool | Descripción |
|------|-------------|
| `analyze_ict_setup` | Análisis completo multi-TF (1H→15m→2m) |
| `get_candles` | Velas OHLCV para cualquier símbolo y timeframe |
| `detect_fvg` | Fair Value Gaps |
| `detect_liquidity` | Swing points, Equal H/L, Sweeps |
| `detect_displacement_ob` | Displacement + Order Blocks |
| `detect_cisd` | Change in State of Delivery (CHoCH) |
| `check_macro` | Macro window ICT actual |
| `market_status` | Precio y estado de sesión |
| `tradingview_webhook_start` | Iniciar receptor de webhooks |
| `tradingview_webhook_status` | Estado del webhook server |
| `tradingview_get_signals` | Consultar señales recibidas |
| `tradingview_latest_signal` | Última señal de TradingView |

---

## Símbolos soportados

| Símbolo | Instrumento |
|---------|-------------|
| `NQ` | Nasdaq 100 E-mini Futures |
| `ES` | S&P 500 E-mini Futures |
| `YM` | Dow Jones E-mini Futures |
| `RTY` | Russell 2000 Futures |
| `GC` | Gold Futures |
| `CL` | Crude Oil Futures |
| `EURUSD` | Euro/Dollar |
| `GBPUSD` | Pound/Dollar |

---

## Sistema de Rating

| Score | Rating | Acción |
|-------|--------|--------|
| 6+ de 8 | **A+** | Ejecutar |
| 5 de 8 | **A** | Ejecutar con precaución |
| 4 de 8 | **B** | Evaluar contexto |
| < 4 | **C** | NO operar |

### Checklist (8 condiciones)

1. HTF Bias definido
2. Reacción en FVG HTF
3. Sweep de liquidez (15m)
4. Displacement + BOS (2m)
5. CISD confirmado (2m)
6. Order Block activo
7. FVG activo (2m)
8. Macro window

---

## Macros ICT

El sistema prioriza señales dentro de ventanas de alta probabilidad:

| Macro | Horario (ET) |
|-------|-------------|
| London Open Kill Zone | 02:00 — 05:00 |
| NY AM Macro 1 | 09:30 — 10:00 |
| NY AM Macro 2 | 10:45 — 11:15 |
| NY Lunch Macro | 11:45 — 12:15 |
| NY PM Macro | 13:30 — 14:00 |
| NY PM Close | 14:45 — 15:15 |

---

## FAQ

**¿Necesito TradingView para usar el agente MCP?**
No. El análisis funciona solo con datos de mercado (yfinance). TradingView es opcional para el indicador visual y los webhooks.

**¿Los datos tienen delay?**
Los datos de yfinance tienen ~15 min de delay para futuros. Para datos en tiempo real, usa los webhooks desde TradingView con tu suscripción.

**¿Funciona fuera de horario?**
Sí, pero el análisis será sobre los datos del último cierre. El agente te avisará si el mercado está cerrado.

**¿Puedo usar esto para trading real?**
Esta herramienta es para **análisis y educación**. Las decisiones de trading son responsabilidad del usuario. No es asesoramiento financiero.

**¿ngrok se desconecta?**
El plan gratuito de ngrok tiene sesiones de ~2 horas. Para uso continuo, considera ngrok Pro o Cloudflare Tunnel (gratis, sin límite de tiempo).

---

## Licencia

MIT

---

## Disclaimer

Este proyecto es una herramienta de análisis técnico basada en conceptos del Modelo ICT 2022. No constituye asesoramiento financiero. Opera bajo tu propio riesgo.
