# 🚀 Scan Space
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
- **Validadores:** Módulo → Revisan → OK (si no pasa → regresa a Devs)
- **Testers:** GIT → clonar

---

## 6. tecnologias

frontend
- nuxt

base de datos
- sql lite

backernd
- python
