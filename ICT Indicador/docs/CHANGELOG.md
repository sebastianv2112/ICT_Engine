# Changelog

Todos los cambios notables del proyecto ICT 2022 Setup Engine.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionamiento según [Semantic Versioning](https://semver.org/lang/es/).

## [0.1.0] — 2026-04-27

### Añadido
- Estructura inicial del proyecto (src/, docs/, .github/agents/)
- Archivo principal `ICT_2022_Setup_Engine.pine` con módulos base
- **Módulo HTF**: Lectura de datos via `request.security()` (1H/4H)
- **Módulo FVG**: Detección de Fair Value Gaps bullish/bearish en LTF
- **Módulo Sweep**: Detección de Equal Highs/Lows y liquidity sweeps
- **Módulo Displacement**: Validación de velas institucionales (body > avg * factor)
- **Módulo Time Filter**: Filtro de macros ICT (09:45, 10:45, 11:45, 14:45 ET)
- **Motor de Setup**: Evaluación de condiciones y sistema de rating (A+/A/B/C)
- **Niveles Operativos**: Entry, SL, BE, TP1 (2R), TP2 (3R)
- **Panel**: Dashboard con checklist visual y niveles en table
- **Alertas**: `alertcondition()` estáticas + `alert()` dinámicas
- Inputs agrupados con `group` y `tooltip` para cada módulo
- Gestión de objetos visuales (limpieza automática de boxes/labels)
- Sub-agentes: ICT Trader, DevOps, PineScript Dev, QA Validator
- Documentación: ARCHITECTURE.md, CHANGELOG.md, copilot-instructions.md

### Pendiente
- Order Blocks (fase 2)
- iFVG tracking y mitigation
- BOS / CHoCH detection en LTF
- SMT Divergence
- PO3 (Power of Three)
