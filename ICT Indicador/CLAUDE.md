# 🧠 ICT 2022 Setup Engine — AI Agent Specification

# 🧩 Filosofía del Modelo

El precio se mueve de liquidez externa → interna → externa

El sistema debe identificar:
•⁠  ⁠Zonas donde el precio busca liquidez
•⁠  ⁠Reacciones institucionales
•⁠  ⁠Desequilibrios (inefficiencies)

---

# Estructura General del Modelo

## 1. HTF Contexto (1H / 4H)

### Objetivo:
Definir el sesgo y zonas clave

### Detectar:
•⁠  ⁠Fair Value Gaps (FVG HTF)
•⁠  ⁠Order Blocks (opcional)
•⁠  ⁠Dirección del flujo

### Condición clave:
Precio reacciona en FVG HTF → activar búsqueda de setup

---

## 2. Activación del Setup

Una vez en zona HTF:

Entrar en modo "Setup Detection"

---

#Lógica del Setup

##Paso 1 — Liquidity Sweep

Detectar:
•⁠  ⁠Equal Highs / Equal Lows
•⁠  ⁠Highs/Lows recientes

### Validación:
•⁠  ⁠Mecha o cierre que rompe liquidez

Sweep confirmado → condición válida

---

##Paso 2 — Displacement

Detectar:
•⁠  ⁠Vela con cuerpo fuerte
•⁠  ⁠Movimiento impulsivo
•⁠  ⁠Ruptura de estructura interna

### Regla:
body > promedio * factor

---

##Paso 3 — Zona de Entrada

Detectar al menos una:
•⁠  ⁠FVG
•⁠  ⁠iFVG
•⁠  ⁠Order Block

### Regla FVG:
Bullish: low > high[2]  
Bearish: high < low[2]

---

##Paso 4 — Confirmación LTF

En 1m / 5m:
•⁠  ⁠CHoCH
•⁠  ⁠BOS
•⁠  ⁠Micro sweep (opcional)

---

#Checklist del Setup

| Condición | Estado |
|----------|--------|
| Bias HTF | ✔️ / ❌ |
| HTF FVG | ✔️ / ❌ |
| Liquidity Sweep | ✔️ / ❌ |
| Displacement | ✔️ / ❌ |
| FVG / iFVG / OB | ✔️ / ❌ |
| Clear Opposite DOL | ✔️ / ❌ |
| SMT Divergence (opcional) | ✔️ / ❌ |

---

#Sistema de Rating

| Score | Rating |
|------|--------|
| 5+ condiciones | A+ |
| 4 condiciones | A |
| 3 condiciones | B |
| <3 condiciones | C |

---

#Output del Indicador

##Visual en Chart
•⁠  ⁠Cajas de FVG
•⁠  ⁠Bloques (OB)
•⁠  ⁠Sweep marcado
•⁠  ⁠Zonas de entrada

##Panel de Setup

Setup Rating: A+  
Entry: XXXXX  
Stop Loss: XXXXX  
Break Even: XXXXX  
TP1: XXXXX  
TP2: XXXXX  

---

##Alertas

Condición:
HTF + Sweep + Displacement + Zona válida

---

#Lógica de Entrada

##Long

1.⁠ ⁠Precio en FVG HTF  
2.⁠ ⁠Sweep de lows  
3.⁠ ⁠Displacement alcista  
4.⁠ ⁠FVG / OB en LTF  
5.⁠ ⁠Entrada en retroceso  

---

##Short

1.⁠ ⁠Precio en FVG HTF  
2.⁠ ⁠Sweep de highs  
3.⁠ ⁠Displacement bajista  
4.⁠ ⁠FVG / OB en LTF  
5.⁠ ⁠Entrada en retroceso  

---

#Filtro de Tiempo

Macros clave:
•⁠  ⁠09:45
•⁠  ⁠10:45
•⁠  ⁠11:45
•⁠  ⁠14:45

---

#Filtros Críticos

Evitar cuando:
•⁠  ⁠No hay displacement claro
•⁠  ⁠Mercado en rango
•⁠  ⁠Sin interacción HTF

---

#Conceptos Clave

## FVG
low > high[2] → bullish  
high < low[2] → bearish  

## Displacement
body > promedio * factor  

## Sweep
•⁠  ⁠Igualación de highs/lows
•⁠  ⁠Liquidez estructural
•⁠  ⁠Evitar mechas aleatorias

---

#Extensiones Futuras

•⁠  ⁠SMT Divergence
•⁠  ⁠Multi-timeframe sync
•⁠  ⁠PO3 (Accumulation → Manipulation → Distribution)
•⁠  ⁠Integración con macros

---

#Resumen

El sistema debe:

1.⁠ ⁠Leer HTF  
2.⁠ ⁠Esperar reacción  
3.⁠ ⁠Detectar sweep  
4.⁠ ⁠Validar displacement  
5.⁠ ⁠Identificar zona  
6.⁠ ⁠Confirmar en LTF  
7.⁠ ⁠Calificar setup  
8.⁠ ⁠Mostrar niveles  
9.⁠ ⁠Generar alertas  

---

#Resultado

Un sistema que:
•⁠  ⁠Filtra ruido
•⁠  ⁠Detecta setups reales
•⁠  ⁠Estandariza decisiones
•⁠  ⁠Sirve como herramienta de ejecución
