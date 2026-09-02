# 🏥 MedicalSuppliesERP - Sistema de Gestión de Ingreso de Insumos Médicos

Prototipo académico de módulo ERP especializado en la recepción y trazabilidad de insumos médicos estériles y no estériles, diseñado para demostrar principios de ingeniería de software aplicados al cumplimiento de Buenas Prácticas de Almacenamiento y Distribución (GDP/GMP) para dispositivos e insumos sanitarios.

## 🎯 Propósito
Proyecto educativo que implementa un flujo de ingreso de insumos médicos con controles de calidad reales, sirviendo como caso de estudio para:
- Arquitectura de servicios desacoplada en Python/Flask
- Modelado de dominio de insumos sanitarios con estados de cuarentena/calidad
- Trazabilidad de lotes cumpliendo principios ALCOA+
- Control de fechas de caducidad y condiciones de almacenamiento
- Testing automatizado con factories y cobertura de edge cases regulatorios
- Gestión consciente de limitaciones técnicas (SQLite) documentadas como decisiones de diseño

## ⚙️ Características Clave Implementadas
- ✅ Recepción parcial con validación contra orden de compra
- ✅ Estado de cuarentena obligatorio hasta verificación de integridad/esterilidad
- ✅ Trazabilidad inmutable de lotes (caducidad, fabricación, liberación)
- ✅ Prevención de facturas duplicadas por proveedor (constraint DB)
- ✅ Auditoría estructurada con valores anterior/nuevo en JSON
- ✅ 20 tests automatizados cubriendo happy path + escenarios de calidad
- ✅ Mitigaciones documentadas para limitaciones de SQLite en entorno académico

## 🏗️ Arquitectura
- **Backend:** Flask + SQLAlchemy
- **Base de Datos:** SQLite (WAL mode) con plan de migración a PostgreSQL documentado
- **Patrones:** Service Layer, Repository, Custom Exceptions, Factory Pattern (tests)
- **Cumplimiento:** Mapeo explícito de funcionalidades a normas GDP/GMP para insumos sanitarios

## ⚠️ Aviso Importante
Este es un proyecto **exclusivamente académico**. No está certificado ni validado para uso en producción sanitaria real. Las mitigaciones de concurrencia son didácticas y no sustituyen las garantías de un RDBMS empresarial.

## 📚 Documentación
- [Arquitectura y Decisiones de Diseño](docs/arquitectura.md)
- [Mapeo Normativo GDP/GMP para Insumos](docs/cumplimiento-normativo.md)
- [Plan de Migración a Producción](docs/migracion-postgresql.md)
- [Diagrama de Estados de Calidad](docs/diagrama-estados.png)
