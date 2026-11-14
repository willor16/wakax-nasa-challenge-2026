# 🚀 Scan Space

> Transcripción en limpio de la pizarra del proyecto (fotos del 13-nov-2026).
> Las palabras marcadas con `(?)` no se leían con claridad y hay que confirmarlas.
>
> **Reto:** NASA Space Apps Challenge 2026 — *Create Health Monitoring Software for Astronauts on Space Missions*.

---

## 0. ⭐ Regla de oro — Los 10 criterios de premios globales

> **Obligatorio:** cada módulo, pantalla, dato, decisión, tarea o commit **debe satisfacer los 10 criterios** de abajo.
> Si algo no aporta a ninguno de ellos, se replantea antes de hacerlo.
> Fuente: [Space Apps — Awards](https://www.spaceappschallenge.org/awards/) y la [Guía de jueces y premios](https://www.spaceappschallenge.org/resources/judging-awards-guide/).

| # | Premio | Qué piden | Cómo lo cumple Scan Space |
|---|---|---|---|
| 1 | **Best Use of Data** | El proyecto que mejor hace accesibles los datos espaciales o los usa en una aplicación única | Usar datasets reales de NASA (OSDR/GeneLab, DONKI) además de datos simulados, y mostrarlos de forma clara |
| 2 | **Best Use of Science** | El uso más válido de la ciencia y/o del método científico | Rangos de referencia y frecuencias de medición respaldados por fuentes citadas |
| 3 | **Best Use of Technology** | El uso más innovador de la tecnología | Detección de anomalías contra la línea base personal; funcionamiento sin conexión con la Tierra |
| 4 | **Best Storytelling** | Comunicar de forma creativa el potencial de los datos abiertos mediante una narrativa | Contar la historia **antes / durante / después** del despegue en la demo y el video |
| 5 | **Best Mission Concept** | El concepto y diseño más plausibles | Respetar limitaciones reales: radiación, poca muestra de sangre/orina, latencia y espacio a bordo |
| 6 | **Galactic Impact** | El mayor potencial de mejorar la vida en la Tierra o en el universo | Que la solución también sirva para telemedicina remota en la Tierra |
| 7 | **Global Connection** | El proyecto que mejor conecta a personas de todo el mundo mediante la tecnología | Varios idiomas, código abierto en repo público, datos en formato estándar (JSON) |
| 8 | **Local Impact** (?) | El mayor impacto en la comunidad local | Caso de uso local: zonas rurales o aisladas, centros de salud remotos |
| 9 | **Most Inspirational** | El proyecto que "conquista corazones" | Foco humano: ánimo, soledad, motivación, rachas |
| 10 | **Art & Technology** (?) | Unir arte y tecnología | UI y visualizaciones cuidadas, con estética espacial |

> `(?)` = descripción oficial no confirmada (la web no abrió por un error de certificado); revisar la redacción exacta.

### Checklist de validación (aplicar a TODO entregable)

- [ ] 1. Best Use of Data — ¿usa o hace accesibles datos espaciales reales?
- [ ] 2. Best Use of Science — ¿está respaldado por ciencia y fuentes citadas?
- [ ] 3. Best Use of Technology — ¿la tecnología aporta algo innovador?
- [ ] 4. Best Storytelling — ¿se puede contar como parte de la historia de la misión?
- [ ] 5. Best Mission Concept — ¿es plausible en una misión real?
- [ ] 6. Galactic Impact — ¿mejora la vida en la Tierra o en el espacio?
- [ ] 7. Global Connection — ¿es abierto y lo puede usar gente de cualquier lugar?
- [ ] 8. Local Impact — ¿tiene aplicación en nuestra comunidad?
- [ ] 9. Most Inspirational — ¿pone a la persona en el centro?
- [ ] 10. Art & Technology — ¿se ve y se siente bien diseñado?

---

## 1. Equipo

| Rol | Integrantes |
|---|---|
| Devs | Wilson, Wilmer, Carlos |
| Testers | Foco (?), Steve, Sandra |

---

## 2. Objetivos (Obj. 1–3)

- Datos de la misión: **antes / durante / después** del despegue

---

## 3. Datos a recolectar

### 3.1 Datos del usuario (biométricos)

- Hora
- Edad
- Sexo
- Altura
- Peso
- Masa muscular
- Densidad ósea
- IMC
- Ritmo cardíaco
- Presión arterial
- Ruido (ambiente)

### 3.2 Datos de misión (directos)

| Manuales | Automáticos |
|---|---|
| Glucosa | Temperatura |
| Auscultaciones (?) | Humedad |
| Sangre | Tiempo de misión |
| Orina | Tiempo de trabajo (interior y exterior) |
| Exámenes de la vista | Saturación de oxígeno |
| Motrices | Ejercicio |

### 3.3 Datos indirectos

- Estado de ánimo
- Sueño
- Nivel de estrés
- Soledad
- Motivación
- Alimentación
- Hidratación

> **Pendiente:** determinar mediante investigación la frecuencia de medición de los indirectos
> (diarios, semanales, mensuales, etc.).

### 3.4 ⚠️ Datos de especial atención (reto Health Monitoring)

El reto se centra en el monitoreo remoto de **salud cardiovascular, sueño, ejercicio y medicación**. Estos datos tienen prioridad sobre el resto:

| Prioridad | Dato | Por qué | Fuente de datos sugerida |
|---|---|---|---|
| 🔴 Alta | **Cardiovascular**: ritmo cardíaco, presión arterial, ECG, saturación de O₂ | La microgravedad altera el sistema cardiovascular | NASA OSDR — datasets OSD-599 y OSD-270 (corazón) |
| 🔴 Alta | **Radiación**: dosis acumulada y eventos solares | Riesgo principal en misiones largas (ver Pendientes #1) | NASA DONKI (clima espacial) / NOAA |
| 🔴 Alta | **Sueño** | Ciclo día/noche alterado, afecta ánimo y rendimiento | Registro diario (automático + manual) |
| 🔴 Alta | **Ejercicio** | Previene pérdida de músculo y hueso | Registro automático por sesión |
| 🔴 Alta | **Medicación** (nuevo: no estaba en la pizarra) | Control de dosis, horarios y efectos | Registro manual con recordatorios (Notificaciones) |
| 🟠 Media | **Densidad ósea / masa muscular** | Se pierden en microgravedad | Mediciones antes / durante / después |
| 🟠 Media | **Estrés, ánimo, soledad** | Aislamiento prolongado | Cuestionarios periódicos (ver 3.3) |

**Reglas para estos datos:**

- **Línea base personal:** comparar a cada astronauta con sus propios valores de antes del despegue, no con promedios de la población.
- **Alertas tempranas:** detectar tendencias antes de que un valor salga del rango seguro.
- **Sin depender de la Tierra:** el análisis debe funcionar a bordo, sin conexión.
- **Aviso:** los datos de tripulación serán simulados; el software es un prototipo y no un dispositivo médico.

---

## 4. App – Menús

- **Inicio de sesión**
- **Perfil** → Datos personales
  - Psicológicos
  - Físicos
- **Rachas**
- **Notificaciones**

---

## 5. Flujo de trabajo

- **Datos:** Investigar → Filtrar → JSON
- **Validadores:** Módulo → Revisan contra el **checklist de los 10 premios (sección 0)** → OK (si no pasa → regresa a Devs)
- **Testers:** GIT → clonar

---

## 6. Herramientas

- GIT
- Agente IA
- Docs
- Repo

---

## 7. Pendientes / Limitaciones (?) — "Li"

1. Radiación
2. Medición directa: sangre, escasa orina (?)
3. Motrices → vista
4. Ultrasonidos
5. Investigar datos indirectos
6. Línea guía para los datos
7. Confirmar la lista oficial de recursos del reto y la descripción de los premios marcados con `(?)` (la web no abrió por un error de certificado)
