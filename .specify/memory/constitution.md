<!--
Sync Impact Report — Amendment 2 (2026-07-20)
=============================================
Version change: 2.0.0 → 3.0.0 (MAJOR)

Motivación: el criterio de recomendación pasa de "mejor relación calidad/precio" a
"mejor ajuste a la complejidad del proyecto". Optimizar coste directamente llevaba a
recomendar modelos insuficientes cuando eran más baratos —el peor de los dos errores,
porque se paga el intento y además no se obtiene el resultado—.

Cambio: el precio deja de ser criterio de decisión. La designación se resuelve por
ajuste (descartar insuficientes → menor exceso de capacidad); el precio se sigue
mostrando siempre y solo desempata entre ajustes idénticos. La decisión económica
queda explícitamente en manos del usuario.

Bump MAJOR porque redefine de forma incompatible el propósito declarado del proyecto y
la restricción de alcance que gobierna la recomendación: ante el mismo proyecto y el
mismo catálogo, la herramienta puede designar ahora un modelo distinto (y más caro) que
antes. Cualquier consumidor que asumiera "la recomendación es la opción más barata
suficiente" deja de ser correcto.

Secciones modificadas:
  - Propósito — criterio redefinido; ahorro como consecuencia, no como criterio
  - Restricciones de Alcance — dos restricciones nuevas (decisión por ajuste; la
    decisión económica es del usuario)

Artefactos alineados con la enmienda:
  ✅ specs/001-model-recommendation/spec.md — FR-008 reescrito; Q1 marcada como
     supersedida y sustituida por Q3
  ✅ specs/001-model-recommendation/data-model.md — Evaluation gana deficit/excess;
     reglas de best_choice y de ordenación reescritas
  ✅ specs/001-model-recommendation/contracts/cli.md — salida y degradación
  ✅ specs/001-model-recommendation/{plan,research,quickstart,tasks}.md
  ✅ src/specjudge/{recommend,rating,domain,cli}.py y render/ — regla implementada
  ✅ README.md — sección "Reading the output" reescrita
  ✅ tests/ — 56 tests en verde; test_recommend.py reescrito sobre la nueva regla

Nota: los principios I–V no cambian. La enmienda afecta al propósito y al alcance,
no a las garantías de privacidad, transparencia, gratuidad, degradación o comunidad.

---
Sync Impact Report — Amendment 1 (2026-07-20)
=============================================
Version change: 1.0.0 → 2.0.0 (MAJOR)

Motivación: el proyecto se publica como open source con audiencia internacional. Toda la
salida al usuario pasa a inglés, incluida la escala de valoración, que la constitución fija
como vocabulario cerrado.

Cambio: la escala pasa de **mal / regular / bien / sobrado** a **poor / fair / good / overkill**.
Bump MAJOR porque redefine de forma incompatible una restricción de alcance normativa: los
valores emitidos por la herramienta (tabla, JSON, HTML) cambian, rompiendo cualquier consumidor
que dependiera de los literales anteriores. La semántica se conserva intacta ('good' = suficiente,
'overkill' = sobrecoste).

Artefactos alineados con la enmienda:
  ✅ specs/001-model-recommendation/spec.md — FR-004, FR-008, Clarifications Q1, US3
  ✅ specs/001-model-recommendation/data-model.md — enum Rating
  ✅ specs/001-model-recommendation/contracts/cli.md — salida y esquema JSON
  ✅ data/rating-rules.yaml — valores de mapping.per_dimension
  ✅ src/specjudge/** — enum Rating y toda la salida al usuario
  ✅ tests/** — 50 tests actualizados y en verde

---
Sync Impact Report — Ratificación inicial
=========================================
Version change: (plantilla sin rellenar) → 1.0.0
Bump rationale: Ratificación inicial. Se define el conjunto completo de principios
y secciones de gobernanza a partir del contenido aportado por el autor.

Principios definidos (nuevos):
  I.   Local-First y Privacidad por Defecto
  II.  Transparencia y Auditabilidad
  III. Sin Dependencias de Pago Obligatorias
  IV.  Degradación Explícita, Nunca Silenciosa
  V.   Diseñado para Evolucionar en Comunidad

Secciones añadidas:
  - Restricciones de Alcance
  - Estándares de Calidad y Contribución
  - Gobernanza

Plantillas revisadas:
  ✅ .specify/templates/plan-template.md — "Constitution Check" es genérico
     (lee las puertas del fichero de constitución en tiempo de ejecución); sin
     cambios necesarios.
  ✅ .specify/templates/spec-template.md — sin referencias a la constitución; sin cambios.
  ✅ .specify/templates/tasks-template.md — sin referencias a la constitución; sin cambios.
  ✅ .claude/skills/speckit-*/ — guía genérica; sin referencias obsoletas específicas de agente.

Follow-up TODOs: ninguno. Todas las variables se resolvieron; no quedan tokens sin rellenar.
-->

# Constitución de SpecJudge

## Propósito

SpecJudge es una herramienta de línea de comandos, open source y local-first, que analiza los
artefactos de Spec-Driven Development de un proyecto (constitución, especificación y tareas) y
recomienda qué modelo de IA del mercado **mejor se ajusta a la complejidad** de ese trabajo
concreto: ni insuficiente para lo que exige, ni más potente de lo que necesita.

El problema que resuelve: al iniciar la implementación de un proyecto definido con SDD, elegir el
modelo a ciegas lleva a dos errores caros. Elegir un modelo demasiado potente para una tarea
sencilla malgasta dinero; elegir uno demasiado limitado para una tarea exigente no produce el
resultado necesario. SpecJudge sitúa la decisión en el momento óptimo del ciclo —cuando los specs
existen pero aún no se ha gastado un solo token en implementar— y la fundamenta en el contenido
real del proyecto.

**El criterio de recomendación es el ajuste, no el precio.** El ahorro es la *consecuencia* de
dimensionar bien —un modelo sobredimensionado es capacidad que se paga y no se usa—, pero no es el
criterio con el que se elige. Un modelo más barato NUNCA debe recomendarse por encima de otro que
se ajusta mejor al trabajo. El precio se muestra siempre, para que el usuario vea qué cuesta cada
opción y pueda decidir con la información delante, pero la herramienta no lo usa para elegir.

Razón: optimizar el coste directamente lleva a recomendar modelos que no hacen el trabajo, que es
el más caro de los dos errores —se paga el intento y además no se obtiene el resultado—. Ajustar a
la complejidad evita los dos errores a la vez y deja la decisión económica, que depende del
presupuesto y del contexto de cada usuario, en manos del usuario.

## Principios Fundamentales

### I. Local-First y Privacidad por Defecto

El análisis de los artefactos del proyecto DEBE poder ejecutarse íntegramente en la máquina del
usuario. El "juez" que evalúa las tareas es un modelo local ejecutado a través de Ollama. Los
specs de un usuario NUNCA se envían a un servicio de terceros como parte del funcionamiento normal
de la herramienta. La decisión sobre qué modelo usar no debe, en sí misma, filtrar el contenido
del proyecto ni incurrir en coste de API.

**Razón**: Los specs contienen la lógica de negocio y las decisiones de diseño del usuario.
Pedirle que los exponga a un tercero solo para decidir qué modelo contratar es inaceptable y
contradice el propósito de la herramienta.

### II. Transparencia y Auditabilidad

La información de referencia sobre qué puede y no puede hacer cada modelo, y cuánto cuesta, DEBE
residir en ficheros de datos legibles por humanos, versionados y editables por la comunidad. Las
valoraciones que produzca la herramienta DEBEN ir acompañadas de una justificación comprensible.
El usuario DEBE poder auditar por qué se le recomienda un modelo y no otro, y corregir la
información de referencia si no está de acuerdo.

**Razón**: Una recomendación de gasto que el usuario no puede inspeccionar no genera confianza. La
transparencia es también lo que permite que la comunidad mantenga el catálogo actualizado sin
depender del autor original.

### III. Sin Dependencias de Pago Obligatorias

El uso del núcleo de la herramienta NUNCA DEBE requerir una clave de API de pago ni una
suscripción. El único requisito de peso es Ollama con al menos un modelo local instalado. Cualquier
integración con servicios de pago, si existiera en el futuro, DEBE ser opcional y estar claramente
marcada como tal.

**Razón**: Una herramienta cuyo fin es ahorrar dinero no debe obligar a gastar dinero para
funcionar. Esto también maximiza su accesibilidad para estudiantes y desarrolladores individuales.

### IV. Degradación Explícita, Nunca Silenciosa

Cuando falte información para dar una recomendación fiable, la herramienta DEBE decirlo de forma
explícita en lugar de emitir un juicio con datos insuficientes. DEBE distinguir entre "no hay
información suficiente del proyecto" y "hay información pero podría haber más". Cuando falte una
dependencia crítica (por ejemplo, Ollama no instalado), DEBE informar de qué falta y cómo
resolverlo, nunca fallar con un error críptico.

**Razón**: Una recomendación de gasto basada en datos pobres es peor que ninguna recomendación. El
usuario debe saber en qué grado puede fiarse del resultado.

### V. Diseñado para Evolucionar en Comunidad

El proyecto se publica como open source con el fin explícito de que otras personas lo mejoren. La
arquitectura DEBE favorecer que un contribuidor pueda añadir un modelo nuevo al catálogo, ajustar
precios o refinar las reglas de evaluación sin tener que reescribir la lógica del programa. La
información volátil (modelos, capacidades, precios) DEBE estar separada del código.

**Razón**: Los modelos y sus precios cambian cada pocas semanas. Si mantenerse al día exigiera
tocar el código, el proyecto quedaría obsoleto en cuanto el autor dejara de mantenerlo. La
separación datos/código es lo que permite que la comunidad lo mantenga vivo.

## Restricciones de Alcance

- SpecJudge recomienda, no ejecuta la implementación. Su salida es un juicio informado, no una
  integración que llame a los modelos evaluados.
- La evaluación se realiza sobre el conjunto de tareas del proyecto de una sola vez, para dar una
  recomendación global de proyecto, no una por tarea.
- El catálogo de modelos es una fuente de referencia mantenida, no un feed en tiempo real. La
  exactitud de los precios depende de que el catálogo esté actualizado, y esto se asume y se
  comunica como tal.
- La valoración cualitativa por modelo se expresa en una escala fija y cerrada:
  **poor / fair / good / overkill**. La escala es un vocabulario cerrado en inglés: `good` es la
  capacidad suficiente (óptimo) y `overkill` denota sobrecoste, nunca mérito.
- La designación del modelo recomendado se decide **exclusivamente por ajuste a la complejidad**:
  se descartan los modelos insuficientes en alguna dimensión y, entre los capaces, gana el de menor
  exceso de capacidad. El precio NO interviene en la decisión; a lo sumo desempata entre modelos
  cuyo ajuste es idéntico, de modo que nunca pueda prevalecer sobre el ajuste.
- SpecJudge no decide por el usuario si el coste le compensa. Muestra el precio de cada opción y le
  deja esa decisión, que depende de su presupuesto y su contexto.

## Estándares de Calidad y Contribución

- Todo cambio en el catálogo de modelos DEBE indicar la fecha de la información de precios para que
  su vigencia sea verificable.
- El comportamiento del programa ante la ausencia de artefactos o de Ollama DEBE estar cubierto de
  forma que un cambio no lo rompa silenciosamente.
- La justificación mostrada al usuario DEBE ser suficiente para que este entienda la recomendación
  sin leer el código.
- Las contribuciones que añadan dependencias de pago obligatorias al núcleo se rechazan por
  principio (ver Principio III).

## Gobernanza

Esta constitución prevalece sobre cualquier otra práctica o preferencia de estilo. Las
especificaciones (`spec.md`), los planes (`plan.md`) y las tareas (`tasks.md`) que se generen para
este proyecto DEBEN ser coherentes con estos principios; cualquier desviación DEBE justificarse de
forma explícita.

Las enmiendas a esta constitución requieren:

1. Una descripción clara del cambio y su motivación.
2. Actualización del número de versión según versionado semántico:
   - **MAJOR**: eliminación o redefinición incompatible de un principio.
   - **MINOR**: adición de un principio o de una sección de guía sustancial.
   - **PATCH**: aclaraciones y correcciones que no cambian el significado.
3. Revisión de que los artefactos dependientes sigan alineados.

**Version**: 3.0.0 | **Ratified**: 2026-07-20 | **Last Amended**: 2026-07-20
