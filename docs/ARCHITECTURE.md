# ICT 2022 Setup Engine — Arquitectura Técnica

## Diagrama de Módulos

```
┌─────────────────────────────────────────────────────────┐
│                    INPUTS (Settings)                     │
│  HTF Config │ Sweep │ Displacement │ FVG │ Panel │ Time │
└──────┬──────┴───┬───┴──────┬───────┴──┬──┴───┬───┴──┬──┘
       │          │          │          │      │      │
       ▼          │          │          │      │      │
┌──────────────┐  │          │          │      │      │
│  HTF Module  │  │          │          │      │      │
│ req.security │  │          │          │      │      │
│ Bias + FVG   │  │          │          │      │      │
└──────┬───────┘  │          │          │      │      │
       │          ▼          ▼          ▼      │      │
       │  ┌────────┐ ┌──────────┐ ┌────────┐  │      │
       │  │ Sweep  │ │  Disp    │ │  FVG   │  │      │
       │  │ Module │ │  Module  │ │ Module │  │      │
       │  │ EqH/L  │ │ body>avg │ │ LTF    │  │      │
       │  └───┬────┘ └────┬─────┘ └───┬────┘  │      │
       │      │           │           │        │      │
       ▼      ▼           ▼           ▼        │      ▼
    ┌──────────────────────────────────────┐    │  ┌────────┐
    │        SETUP ENGINE (Rating)         │◄───┘  │ Time   │
    │  Combina condiciones → Score → A+/A  │◄──────│ Filter │
    └──────────┬───────────────┬───────────┘       └────────┘
               │               │
       ┌───────▼──────┐  ┌────▼─────┐
       │   VISUALS    │  │  PANEL   │
       │ Boxes/Labels │  │  Table   │
       │ FVG, Sweep   │  │ Checklist│
       └──────────────┘  │ Niveles  │
                         └────┬─────┘
                              │
                         ┌────▼─────┐
                         │ ALERTAS  │
                         │ A+ / A   │
                         └──────────┘
```

## Módulos del Indicador

### 1. Inputs (Líneas ~30-85)
Todos los `input()` agrupados por módulo con `group` y `tooltip`.

| Grupo | Función |
|-------|---------|
| HTF — Contexto | Timeframe HTF, toggles de FVG/OB |
| Liquidity Sweep | Lookback, tolerancia Equal H/L |
| Displacement | Factor multiplicador, período SMA |
| FVG / iFVG | Colores, toggle mitigación |
| Order Blocks | Colores (fase 2) |
| Panel & Alertas | Posición, rating mínimo |
| Filtro de Tiempo | Macros ICT activables |

### 2. HTF Module (Líneas ~95-105)
- `request.security()` para obtener OHLC del timeframe superior
- Detección de FVG en HTF vía security
- **Restricción**: todas las llamadas son top-level

### 3. FVG Module (Líneas ~110-125)
- `fvg_isBullish()`: `low > high[2]`
- `fvg_isBearish()`: `high < low[2]`
- Dibuja boxes con colores configurables
- Gestiona limpieza de boxes antiguos

### 4. Displacement Module (Líneas ~130-145)
- `disp_validate()`: `bodySize > avgBody * factor`
- `disp_isBullish()` / `disp_isBearish()`
- Usa `ta.sma()` para calcular promedio de cuerpos

### 5. Sweep Module (Líneas ~150-185)
- `sweep_findEqualHighs()` / `sweep_findEqualLows()`: busca en lookback
- `sweep_highsSwept()` / `sweep_lowsSwept()`: confirma barrido
- Dibuja labels con iconos de sweep

### 6. Time Filter (Líneas ~190-205)
- `time_inMacroWindow()`: verifica macros ICT en hora NYSE
- Ventanas de ±15 minutos por macro

### 7. Setup Engine (Líneas ~230-260)
- Cuenta condiciones cumplidas por dirección (LONG/SHORT)
- `setup_getRating(score)`: convierte score a A+/A/B/C
- Activa setup si score >= B y dentro de ventana temporal

### 8. Niveles Operativos (Líneas ~265-280)
- Entry: zona del FVG
- SL: beyond del FVG + buffer
- BE: Entry + 50% del riesgo
- TP1: 2R | TP2: 3R

### 9. Panel (Líneas ~285-340)
- `table.new()` con checklist visual (✔️/❌)
- Muestra rating con color coding
- Niveles Entry/SL/TP1/TP2

### 10. Alertas (Líneas ~345-370)
- `alertcondition()`: para configuración estática en TradingView
- `alert()`: dinámica con rating y score

## Flujo de Datos

```
HTF OHLC (request.security)
    ├── htfBullBias / htfBearBias
    └── htfFvgBull / htfFvgBear
         │
LTF Current Bar
    ├── fvg_isBullish / fvg_isBearish → bullFVG / bearFVG
    ├── disp_validate → bullDisp / bearDisp
    └── sweep_check → sweepHighs / sweepLows
         │
    ┌────▼────┐
    │ longScore = sum(condiciones bullish) │
    │ shortScore = sum(condiciones bearish) │
    └────┬────┘
         │
    Rating → Panel → Alertas
```

## Limitaciones Técnicas

| Limitación | Mitigation |
|-----------|------------|
| ~500 boxes max | Array tracking + cleanup |
| ~500 labels max | Array tracking + cleanup |
| No imports | Single-file architecture |
| request.security top-level | Pre-compute all HTF data |
| Replay mode | Avoid barstate.isrealtime, timenow |

## Roadmap

| Versión | Feature |
|---------|---------|
| v0.1.0 | FVG + Sweep + Displacement + Panel + Alertas |
| v0.2.0 | Order Blocks, iFVG mitigation tracking |
| v0.3.0 | SMT Divergence, BOS/CHoCH en LTF |
| v0.4.0 | PO3 detection, Killzone integration |
| v1.0.0 | Sistema completo con todos los módulos |
