# Casos a revisar según la guía de límites

Generado con `python ml/ner/revision_corpus.py` a partir de `corpus_entidades.json`. No edites este fichero a mano: cambia el corpus y vuelve a generarlo. La guía está en `GUIA_LIMITES.md`.

**78 propuestas** (55 en `dev`, 23 en `test`). Son orientativas: decide el revisor aplicando la prueba de la mención mínima. Las del `test` se corrigen con las mismas reglas, sin mirar ningún resultado del sistema sobre esos casos.

| Regla | Propuestas |
| :--- | ---: |
| L1 · Intensidad o gravedad en el borde | 28 |
| L2 · Artículo indefinido inicial | 9 |
| L3 · Verbo de marco inicial | 8 |
| L4 · Instrumento o circunstancia de la lesión | 4 |
| L5 · Tiempo, número de veces o desencadenante | 4 |
| L6 · Gestación sin anotar (con su edad gestacional) | 1 |
| L7 · Hallazgo normal sin anotar como negado | 5 |
| L8 · Evento traumático sin anotar | 7 |
| L9 · Tipo de entidad | 3 |
| A1 · Texto anotado en otros casos y aquí no | 8 |
| A2 · Borde en palabra funcional | 1 |

## L1 · Intensidad o gravedad en el borde

| Caso | Split | Tipo | Span actual | Propuesta | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| B004 | dev | symptoms | `sangrando muchísimo` | sangrando | comprobar que lo que queda sigue siendo el mismo hallazgo |
| B030 | dev | symptoms | `Mareo muy fuerte` | Mareo | comprobar que lo que queda sigue siendo el mismo hallazgo |
| B031 | dev | symptoms | `me pica mucho` | me pica | comprobar que lo que queda sigue siendo el mismo hallazgo |
| B034 | dev | symptoms | `muy hinchado` | hinchado | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N006 | dev | symptoms | `dificultad respiratoria severa` | dificultad respiratoria | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N009 | dev | symptoms | `muy confundido` | confundido | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N014 | dev | symptoms | `dolor de cabeza muy fuerte` | dolor de cabeza | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N017 | dev | symptoms | `muy confundido` | confundido | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N018 | dev | symptoms | `dolor de cabeza intenso` | dolor de cabeza | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N028 | dev | symptoms | `sangra poquito` | sangra | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N038 | dev | symptoms | `un poco roja` | roja | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N072 | dev | symptoms | `palidez marcada` | palidez | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N082 | dev | symptoms | `sudando mucho` | sudando | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N107 | dev | symptoms | `mucha sed` | sed | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N108 | dev | symptoms | `me duele mucho` | me duele | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N109 | dev | symptoms | `orino muy poquito` | orino | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N115 | dev | symptoms | `tose mucho` | tose | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N122 | dev | diagnoses | `trauma craneal leve` | trauma craneal | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N147 | dev | symptoms | `dolor leve` | dolor | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N147 | dev | diagnoses | `esguince de tobillo grado I` | esguince de tobillo | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N154 | dev | symptoms | `un poco morado` | morado | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N173 | dev | diagnoses | `acné leve` | acné | comprobar que lo que queda sigue siendo el mismo hallazgo |
| B016 | test | symptoms | `dolor de cabeza muy fuerte` | dolor de cabeza | comprobar que lo que queda sigue siendo el mismo hallazgo |
| B047 | test | symptoms | `muy ansioso` | ansioso | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N010 | test | symptoms | `babeando mucho` | babeando | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N016 | test | symptoms | `mucha sed` | sed | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N016 | test | symptoms | `orina mucho` | orina | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N023 | test | symptoms | `muy hinchada` | hinchada | comprobar que lo que queda sigue siendo el mismo hallazgo |

## L2 · Artículo indefinido inicial

| Caso | Split | Tipo | Span actual | Propuesta | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| B038 | dev | diagnoses | `una herida que sangra` | herida que sangra | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N004 | dev | history | `una válvula en el corazón` | válvula en el corazón | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N035 | dev | diagnoses | `un nacido en la axila` | nacido en la axila | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N048 | dev | diagnoses | `un lunar` | lunar | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N143 | dev | diagnoses | `una muela picada` | muela picada | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N165 | dev | symptoms | `unas manchitas en la cara` | manchitas en la cara | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N169 | dev | diagnoses | `una verruga en el dedo` | verruga en el dedo | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N178 | dev | diagnoses | `un lunar` | lunar | comprobar que lo que queda sigue siendo el mismo hallazgo |
| B059 | test | symptoms | `una mancha en la piel` | mancha en la piel | comprobar que lo que queda sigue siendo el mismo hallazgo |

## L3 · Verbo de marco inicial

| Caso | Split | Tipo | Span actual | Propuesta | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| B015 | dev | symptoms | `sigue muy dormido` | dormido | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N060 | dev | symptoms | `se está poniendo azulito` | azulito | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N108 | dev | symptoms | `está hinchada` | hinchada | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N116 | dev | symptoms | `está morado` | morado | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N119 | dev | symptoms | `Siento que me voy a morir` | me voy a morir | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N023 | test | symptoms | `está torcida` | torcida | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N063 | test | symptoms | `está como tiesa` | tiesa | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N066 | test | diagnoses | `tiene quemado el pecho, los brazos y la cara` | quemado el pecho, los brazos y la cara | comprobar que lo que queda sigue siendo el mismo hallazgo |

## L4 · Instrumento o circunstancia de la lesión

| Caso | Split | Tipo | Span actual | Propuesta | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| B024 | dev | diagnoses | `Quemadura con aceite hirviendo en toda la pierna` | Quemadura | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N019 | dev | diagnoses | `Me corté la muñeca con un vidrio` | Me corté la muñeca | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N154 | dev | diagnoses | `Me golpeé el dedo con la puerta` | Me golpeé el dedo | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N064 | test | diagnoses | `Lo chuzaron en el pecho con un cuchillo` | Lo chuzaron en el pecho | comprobar que lo que queda sigue siendo el mismo hallazgo |

## L5 · Tiempo, número de veces o desencadenante

| Caso | Split | Tipo | Span actual | Propuesta | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| N128 | dev | symptoms | `vomitó cinco veces` | vomitó | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N143 | dev | symptoms | `me duele cuando tomo algo frío` | me duele | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N024 | test | symptoms | `no he orinado desde la mañana` | no he orinado | comprobar que lo que queda sigue siendo el mismo hallazgo |
| N086 | test | symptoms | `me mareo cuando me paro` | me mareo | comprobar que lo que queda sigue siendo el mismo hallazgo |

## L6 · Gestación sin anotar (con su edad gestacional)

| Caso | Split | Tipo | Span actual | Propuesta | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| B025 | test | diagnoses | — | añadir diagnoses: «Gestante» |  |

## L7 · Hallazgo normal sin anotar como negado

| Caso | Split | Tipo | Span actual | Propuesta | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| N103 | dev | symptoms | — | añadir symptoms: «consciente» (negated: true) |  |
| N124 | dev | symptoms | — | añadir symptoms: «saturación normal» (negated: true) |  |
| N147 | dev | symptoms | — | añadir symptoms: «marcha conservada» (negated: true) |  |
| N132 | test | symptoms | — | añadir symptoms: «consciente» (negated: true) |  |
| N138 | test | symptoms | — | añadir symptoms: «comiendo bien» (negated: true) |  |

## L8 · Evento traumático sin anotar

| Caso | Split | Tipo | Span actual | Propuesta | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| B002 | dev | diagnoses | — | añadir diagnoses: «accidente de moto» |  |
| N001 | dev | diagnoses | — | añadir diagnoses: «choque» |  |
| N002 | dev | diagnoses | — | añadir diagnoses: «se cayó» |  |
| N108 | dev | diagnoses | — | añadir diagnoses: «Me caí» |  |
| B010 | test | diagnoses | — | añadir diagnoses: «Atropellado por un bus» |  |
| B018 | test | diagnoses | — | añadir diagnoses: «Se cayó de la bicicleta» |  |
| N023 | test | diagnoses | — | añadir diagnoses: «Me caí de la escalera» |  |

## L9 · Tipo de entidad

| Caso | Split | Tipo | Span actual | Propuesta | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| B049 | dev | symptoms | `deshidratación` | deshidratación → diagnoses | nombre de síndrome; «signos de deshidratación» sí es symptoms |
| N108 | dev | diagnoses | `la muñeca me quedó chueca` | la muñeca me quedó chueca → symptoms | deformidad observada: es un signo aunque sugiera una fractura |
| N123 | dev | symptoms | `cólico renal izquierdo` | cólico renal izquierdo → diagnoses | nombre de síndrome |

## A1 · Texto anotado en otros casos y aquí no

| Caso | Split | Tipo | Span actual | Propuesta | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| N002 | dev | — | — | valorar «el azúcar» | inyecta insulina, le medimos el azúcar y salió en 35. |
| N008 | dev | — | — | valorar «convulsión» | omo veinte minutos, le da una convulsión tras otra sin despertar entre |
| N078 | dev | — | — | valorar «oxígeno» | turación de 78 por ciento con oxígeno y frecuencia respiratoria de |
| N133 | dev | — | — | valorar «el azúcar» | Soy diabético, el azúcar me dio 320 en la mañana y ten |
| N157 | dev | — | — | valorar «dolor» | ca desde que me apoyé mal, el dolor es como un 3 de 10. |
| N073 | test | — | — | valorar «medicamentos» | cuando le hablamos; no tomaba medicamentos. |
| N126 | test | — | — | valorar «está hinchada» | a, pero sí puedo caminar y no está hinchada. |
| N131 | test | — | — | valorar «dolor» | Me duele el oído derecho, el dolor es como un 6 de 10 y salió un |

## A2 · Borde en palabra funcional

| Caso | Split | Tipo | Span actual | Propuesta | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| B010 | test | diagnoses | `en el tórax` | — | el span parece incompleto |
