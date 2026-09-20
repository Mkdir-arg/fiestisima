# 15 · Roadmap

## Fase 0 — Base (semana 1)
- [x] Repo, scaffold Expo + Supabase, migración inicial
- [ ] Auth con email/password, pantalla Login, sesión persistente
- [ ] Catálogo básico: lista, alta, edición
- [ ] Deploy web en Vercel + proyecto Supabase staging

## Fase 1 — MVP (semanas 2-5)
- [ ] Escaneo de código de barras + alta rápida con Open Food Facts
- [ ] Registra carico completo (lote, scadenza, fornitore, cantidad, precio, foto DDT)
- [ ] Scarico y scarto con FEFO
- [ ] Scadenze con agrupación y umbral configurable
- [ ] Push: resumen diario + alertas
- [ ] Stock, mínimos, `Sotto scorta`
- [ ] Fornitori ABM
- [ ] Registro de trazabilidad con filtros + PDF
- [ ] Utenti: invitaciones, roles, RLS completa
- [ ] Dashboard web
- [ ] TestFlight con la cliente. **Meta: una semana de uso real registrando todo lo que entra.**

## Fase 1.1 — Ajustes tras la prueba (semana 6)
- [ ] Lo que surja de la semana de uso
- [ ] OCR de lote y fecha (requiere dev build)
- [ ] Offline parcial con cola
- [ ] Excel

## Fase 2 — Ampliaciones
- [ ] Foto de fattura/DDT → carico múltiple
- [ ] QR interno imprimible para preparaciones propias y productos sfusi
- [ ] Modo escaneo continuo
- [ ] Lista de compra con WhatsApp Business API (confirmaciones automáticas)
- [ ] Registro de temperaturas HACCP (frigos y freezers, dos veces al día)
- [ ] Alérgenos por producto y por preparación
- [ ] Offline completo
- [ ] Multi-negocio (misma app para otra attività)

## Criterio para pasar de fase
La cliente usa la app en lugar del cuaderno durante una semana completa sin volver al papel. Si vuelve al papel, la fase no terminó.
