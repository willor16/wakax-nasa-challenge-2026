# 🚀 SCAN SPACE — Abstracción de Ideas del Proyecto

> **Propósito:** Documento de consolidación y lluvia de ideas preliminares de la solución, parámetros de salud a monitorear, funcionalidades de la aplicación y flujo de trabajo del equipo.  
> *(Nota: Toda la documentación, reglas del concurso y requerimientos oficiales de la NASA se encuentran en `../wakax-docs/investigacion/RETO_OFICIAL_NASA_2026.md`).*

---

## 1. Alcance y Fases Temporales de la Misión

Estructuración conceptual del monitoreo de salud del astronauta a lo largo del arco de vuelo espacial:

* **Fase 1: Antes del Despegue (Pre-Vuelo)**
  * Captura de la línea base individual de salud del astronauta en condiciones terrestres ($1G$).
  * Registro de valores de referencia clínicos y capacidades basales.
* **Fase 2: Durante el Vuelo / Tránsito (En Misión)**
  * Monitoreo continuo de adaptación aguda, estrés de despegue y seguimiento diario en microgravedad.
  * Detección temprana de degradación física y psicológica en espacio profundo.
* **Fase 3: Después / En Superficie (Post-Vuelo / Regeneración)**
  * Evaluación del impacto fisiológico en gravedad parcial (Luna/Marte) o tras el retorno a la Tierra.
  * Protocolos de recuperación y seguimiento de remodelación ósea y muscular.

---

## 2. Taxonomía de Datos a Recolectar (Lluvia de Parámetros)

### 2.1 Datos del Usuario (Perfil Biométrico Base)
* Hora / Marca temporal del registro
* Edad
* Sexo biológico
* Altura
* Peso corporal
* Masa muscular
* Densidad mineral ósea
* Índice de Masa Corporal (IMC)
* Ritmo cardíaco en reposo
* Presión arterial basal
* Ruido ambiental de referencia

### 2.2 Datos de Misión (Directos y Operativos)

| Categoría | Parámetros Propuestos |
|---|---|
| **Automáticos (Sensores / Cabina)** | • Temperatura de cabina<br>• Humedad relativa<br>• Tiempo de misión transcurrido<br>• Tiempo de trabajo (interior IVA vs. exterior EVA)<br>• Saturación de oxígeno ($SpO_2$)<br>• Carga de ejercicio realizado |
| **Manuales / Clínicos (Point-of-Care)** | • Glucosa en sangre<br>• Auscultación cardiopulmonar<br>• Análisis de muestras de sangre<br>• Análisis de muestras de orina (hidratación y electrolitos)<br>• Exámenes de la vista (monitoreo de agudeza visual / SANS)<br>• Pruebas de destreza motriz y cognitiva |

### 2.3 Datos Indirectos (Salud Mental, Conductual y Bienestar)
* Estado de ánimo
* Calidad y horas de sueño
* Nivel de estrés percibido
* Sensación de aislamiento / soledad
* Nivel de motivación
* Registro de alimentación
* Registro de hidratación

> **Punto a definir:** Determinar mediante investigación médica la frecuencia óptima de registro para los datos indirectos (diarios, semanales o por eventos) para no sobrecargar la rutina del astronauta.

---

## 3. Módulos y Funcionalidades Iniciales de la Aplicación

* **Inicio de Sesión / Identificación:** Perfil individual de cada tripulante para cargar su historial clínico personalizado.
* **Perfil de Astronauta:** Panel interactivo con desglose de datos físicos (constantes vitales) y psicológicos (estado general).
* **Rachas y Hábitos (*Engagement*):** Mecánica visual de constancia para motivar el cumplimiento diario de registros y ejercicio sin generar fricción.
* **Notificaciones y Alertas:** Avisos preventivos para toma de mediciones de rutina o recordatorios de descanso activo.

---

## 4. Dinámica de Trabajo y Validación del Equipo

* **Flujo de Datos:** Investigar $\rightarrow$ Filtrar fuentes confiables $\rightarrow$ Estructurar en formato JSON.
* **Flujo de Validación:** Modelado en Módulo $\rightarrow$ Revisión cruzada en parejas $\rightarrow$ Visto bueno / Ajuste técnico.
