#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ICT Pine Script Static Validator
# Analiza el archivo .pine buscando errores comunes, incompatibilidades
# con replay mode, límites de TradingView, y convenciones del proyecto.
# ═══════════════════════════════════════════════════════════════════

PINE_FILE="${1:-src/ICT_2022_Setup_Engine.pine}"
ERRORS=0
WARNINGS=0

# Colores
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ((ERRORS++))
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNINGS++))
}

print_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

echo "═══════════════════════════════════════════════════════"
echo "  ICT Pine Script Validator"
echo "  Archivo: $PINE_FILE"
echo "═══════════════════════════════════════════════════════"
echo ""

# --- Verificar que el archivo existe ---
if [ ! -f "$PINE_FILE" ]; then
    print_error "Archivo no encontrado: $PINE_FILE"
    exit 2
fi

CONTENT=$(cat "$PINE_FILE")
LINE_COUNT=$(wc -l < "$PINE_FILE")

# ═══════════════════════════════════════════════════════════════════
# 1. Versión Pine Script
# ═══════════════════════════════════════════════════════════════════
echo "--- Verificación de versión ---"
if echo "$CONTENT" | grep -qE '//@version=(5|6)'; then
    VERSION=$(echo "$CONTENT" | grep -oE '//@version=[0-9]+')
    print_ok "Pine Script $VERSION detectado"
else
    print_error "No se encontró //@version=5 o //@version=6"
fi

# ═══════════════════════════════════════════════════════════════════
# 2. Declaración indicator()
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "--- Declaración del indicador ---"
if echo "$CONTENT" | grep -q 'indicator('; then
    print_ok "indicator() declarado"
else
    print_error "No se encontró indicator() — requerido"
fi

if echo "$CONTENT" | grep -q 'strategy('; then
    print_error "strategy() detectado — este proyecto usa indicator(), no strategy()"
fi

# ═══════════════════════════════════════════════════════════════════
# 3. Compatibilidad Replay Mode
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "--- Compatibilidad Replay Mode ---"

# barstate.isrealtime NO funciona en replay
REALTIME_LINES=$(grep -n 'barstate\.isrealtime' "$PINE_FILE" || true)
if [ -n "$REALTIME_LINES" ]; then
    while IFS= read -r line; do
        print_error "barstate.isrealtime en línea $(echo "$line" | cut -d: -f1) — NO funciona en replay mode"
    done <<< "$REALTIME_LINES"
else
    print_ok "No usa barstate.isrealtime"
fi

# timenow tiene comportamiento diferente en replay
TIMENOW_LINES=$(grep -n 'timenow' "$PINE_FILE" || true)
if [ -n "$TIMENOW_LINES" ]; then
    while IFS= read -r line; do
        print_warning "timenow en línea $(echo "$line" | cut -d: -f1) — comportamiento diferente en replay"
    done <<< "$TIMENOW_LINES"
else
    print_ok "No usa timenow"
fi

# ═══════════════════════════════════════════════════════════════════
# 4. request.security() correctamente usado
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "--- request.security() ---"

# Verificar que NO usa security() deprecado
DEPRECATED_SEC=$(grep -n '[^.]security(' "$PINE_FILE" | grep -v 'request\.security' | grep -v '//' || true)
if [ -n "$DEPRECATED_SEC" ]; then
    while IFS= read -r line; do
        print_error "security() deprecado en línea $(echo "$line" | cut -d: -f1) — usar request.security()"
    done <<< "$DEPRECATED_SEC"
else
    print_ok "No usa security() deprecado"
fi

# Contar llamadas a request.security
SEC_COUNT=$(grep -c 'request\.security' "$PINE_FILE" || true)
print_info "request.security() llamadas: $SEC_COUNT"
if [ "$SEC_COUNT" -gt 40 ]; then
    print_warning "Más de 40 llamadas a request.security() — posible impacto en performance"
fi

# Verificar que request.security NO esté dentro de if/for (indentado)
# Heurística: líneas con request.security que tienen indentación de 8+ espacios (dentro de bloque)
SEC_IN_SCOPE=$(grep -n '        request\.security\|	request\.security' "$PINE_FILE" | grep -v '//' || true)
if [ -n "$SEC_IN_SCOPE" ]; then
    while IFS= read -r line; do
        print_warning "request.security() posiblemente dentro de scope local en línea $(echo "$line" | cut -d: -f1) — debe ser top-level"
    done <<< "$SEC_IN_SCOPE"
else
    print_ok "request.security() parece estar en top-level"
fi

# ═══════════════════════════════════════════════════════════════════
# 5. Gestión de objetos visuales
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "--- Objetos visuales ---"

BOX_NEW=$(grep -c 'box\.new' "$PINE_FILE" || true)
LABEL_NEW=$(grep -c 'label\.new' "$PINE_FILE" || true)
LINE_NEW=$(grep -c 'line\.new' "$PINE_FILE" || true)
TABLE_NEW=$(grep -c 'table\.new' "$PINE_FILE" || true)

print_info "box.new(): $BOX_NEW | label.new(): $LABEL_NEW | line.new(): $LINE_NEW | table.new(): $TABLE_NEW"

# Verificar que hay delete para cada tipo creado
if [ "$BOX_NEW" -gt 0 ] && ! grep -q 'box\.delete' "$PINE_FILE"; then
    print_error "Crea boxes pero nunca los elimina — riesgo de exceder límite"
fi

if [ "$LABEL_NEW" -gt 0 ] && ! grep -q 'label\.delete' "$PINE_FILE"; then
    print_error "Crea labels pero nunca los elimina — riesgo de exceder límite"
fi

if [ "$LINE_NEW" -gt 0 ] && ! grep -q 'line\.delete' "$PINE_FILE"; then
    print_error "Crea lines pero nunca los elimina — riesgo de exceder límite"
fi

if [ "$TABLE_NEW" -gt 0 ] && ! grep -q 'table\.delete' "$PINE_FILE"; then
    print_warning "Crea tables pero no se detectó table.delete()"
fi

# Verificar max_boxes_count en indicator()
if echo "$CONTENT" | grep -q 'max_boxes_count'; then
    print_ok "max_boxes_count configurado"
else
    if [ "$BOX_NEW" -gt 0 ]; then
        print_warning "Crea boxes pero no tiene max_boxes_count en indicator()"
    fi
fi

# ═══════════════════════════════════════════════════════════════════
# 6. Convenciones de código del proyecto
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "--- Convenciones de código ---"

# Verificar que inputs tienen group
INPUTS_WITHOUT_GROUP=$(grep -n 'input\.\(int\|float\|bool\|string\|color\|timeframe\)(' "$PINE_FILE" | grep -v 'group' | grep -v '//' || true)
if [ -n "$INPUTS_WITHOUT_GROUP" ]; then
    while IFS= read -r line; do
        print_warning "Input sin 'group' en línea $(echo "$line" | cut -d: -f1)"
    done <<< "$INPUTS_WITHOUT_GROUP"
else
    print_ok "Todos los inputs tienen group"
fi

# Verificar prefijo de funciones (convención: modulo_funcion)
FUNCS=$(grep -n '^[a-zA-Z_][a-zA-Z0-9_]*(.*)' "$PINE_FILE" | grep '=>' || true)
if [ -n "$FUNCS" ]; then
    FUNCS_NO_PREFIX=$(echo "$FUNCS" | grep -v '_' || true)
    if [ -n "$FUNCS_NO_PREFIX" ]; then
        while IFS= read -r line; do
            print_warning "Función sin prefijo de módulo en línea $(echo "$line" | cut -d: -f1): $(echo "$line" | cut -d: -f2 | sed 's/(.*//')"
        done <<< "$FUNCS_NO_PREFIX"
    else
        print_ok "Funciones siguen convención de prefijo"
    fi
fi

# ═══════════════════════════════════════════════════════════════════
# 7. Variables persistentes
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "--- Variables persistentes ---"
VAR_COUNT=$(grep -c '^var ' "$PINE_FILE" || true)
VARIP_COUNT=$(grep -c '^varip ' "$PINE_FILE" || true)
print_info "var declarations: $VAR_COUNT | varip declarations: $VARIP_COUNT"

if [ "$VARIP_COUNT" -gt 0 ]; then
    print_warning "varip detectado — solo funciona en tiempo real (no en histórico/replay)"
fi

# ═══════════════════════════════════════════════════════════════════
# 8. Tamaño del archivo
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "--- Métricas ---"
print_info "Líneas totales: $LINE_COUNT"
if [ "$LINE_COUNT" -gt 1000 ]; then
    print_warning "Archivo > 1000 líneas — considerar documentar secciones"
fi
if [ "$LINE_COUNT" -gt 2000 ]; then
    print_warning "Archivo > 2000 líneas — puede afectar legibilidad"
fi

# ═══════════════════════════════════════════════════════════════════
# RESUMEN
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════"
if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo -e "  ${GREEN}✔ VALIDACIÓN EXITOSA${NC} — Sin errores ni advertencias"
elif [ "$ERRORS" -eq 0 ]; then
    echo -e "  ${YELLOW}⚠ VALIDACIÓN CON ADVERTENCIAS${NC} — $WARNINGS advertencia(s)"
else
    echo -e "  ${RED}✖ VALIDACIÓN FALLIDA${NC} — $ERRORS error(es), $WARNINGS advertencia(s)"
fi
echo "═══════════════════════════════════════════════════════"

exit $ERRORS
