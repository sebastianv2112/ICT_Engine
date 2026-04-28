# ICT MCP + TradingView — Guía de Setup

## Arquitectura

```
TradingView (Pine Script v6)
  │  alert() con JSON
  ▼
ngrok/cloudflare tunnel (HTTPS)
  │
  ▼
MCP Webhook Server (localhost:8642)
  │
  ▼
Claude (via @ict-mcp-agent)
  → consulta señales
  → valida con datos OHLCV
  → responde al trader
```

## Paso 1 — Copiar indicador a TradingView

1. Abre TradingView → Pine Editor (pestaña inferior)
2. Crea nuevo script → borra el contenido
3. Copia todo el contenido de `src/ICT_2022_Setup_Engine.pine`
4. Click "Add to chart"
5. El indicador aparecerá con el panel ICT en la esquina superior derecha

## Paso 2 — Configurar Webhook

### Opción A: ngrok (recomendado para testing)

```bash
# Instalar ngrok
brew install ngrok

# Exponer puerto del MCP
ngrok http 8642
```

Copia la URL HTTPS que aparece (ej: `https://abc123.ngrok-free.app`)

### Opción B: Cloudflare Tunnel (producción)

```bash
brew install cloudflare/cloudflare/cloudflared
cloudflared tunnel --url http://localhost:8642
```

## Paso 3 — Crear Alerta en TradingView

1. En TradingView, click en el reloj (Alerts) → "Create Alert"
2. Condition: selecciona tu indicador "ICT 2022 — Flow X"
3. Elige la alerta:
   - **ICT LONG — En OB** → para señales long
   - **ICT SHORT — En OB** → para señales short
   - **ICT Bear/Bull Impulso** → para alertas de impulso
4. **Notifications** → activa "Webhook URL"
5. Pega la URL de ngrok/cloudflare
6. Click "Create"

> **Nota**: Crea 4 alertas separadas (long, short, bear impulso, bull impulso)
> para recibir todos los eventos.

## Paso 4 — Usar el Agente

En VS Code, invoca el agente:

```
@ict-mcp-agent ¿hay señal nueva en NQ?
@ict-mcp-agent analiza NQ completo
@ict-mcp-agent estado del webhook
```

## JSON que envía el indicador

### Señal de entrada (long/short)
```json
{
  "type": "long",
  "symbol": "NQ1!",
  "entry": 27456.0,
  "sl": 27444.0,
  "tp": 27492.0,
  "sl_distance": 12.0,
  "rr": 3.0,
  "checklist": {
    "bias": "bullish",
    "sweep": true,
    "ob": true,
    "ob_zone": "27448-27456",
    "in_macro": true
  }
}
```

### Impulso
```json
{
  "type": "impulse",
  "direction": "bearish",
  "symbol": "NQ1!",
  "ob_top": 27412.75,
  "ob_bot": 27403.0
}
```

## Troubleshooting

| Problema | Solución |
|----------|----------|
| No llegan señales | Verifica ngrok corriendo + URL correcta en TradingView |
| "Webhook server detenido" | El MCP server se reinicia con cada sesión de VS Code |
| Señales repetidas | `alert.freq_once_per_bar` previene duplicados por barra |
| ngrok expira | Free tier dura ~2h. Usa cloudflare para producción |
