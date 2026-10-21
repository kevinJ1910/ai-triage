# Guía de límites de las menciones

**Estado:** propuesta del 17-10-2026. El clínico tiene que aprobarla antes de aplicarla, sobre todo las reglas L7 y L8, que cambian criterios de la guía anterior.

Complementa la [guía de anotación](README.md#guía-de-anotación) del corpus. Esa guía dice qué se anota. Esta dice **dónde empieza y dónde acaba cada mención**, que es donde más se equivocaba el corpus.

## Por qué hace falta

En la validación cruzada del NER sobre `dev` (corrida del 17-10-2026), la mitad de los errores fueron de límites: el modelo encontraba la mención, pero la cortaba distinto que la anotación. La parcial fue 0,917, mientras que la exacta fue 0,777. En muchos de esos casos no se equivocaba el modelo, sino que la anotación era incoherente:

| En un caso | En otro |
| :--- | :--- |
| `muy confundido` (con el «muy») | `pálido` en «muy pálido» (sin el «muy») |
| `Me corté la muñeca con un vidrio` (con el instrumento) | `Me quemé la mano` en «…con agua hirviendo» (sin él) |
| `un lunar` (con artículo) | `manchitas` y `lunar` en otras frases |
| `caída` y `Se cayó del andamio` anotados | `se cayó`, `un choque` y `Me caí` sin anotar |

Con anotaciones así, ninguna métrica exacta es fiable, sea la del modelo, la de las reglas o la de Gemini. Unificar el criterio beneficia a todos los motores por igual.

**Cómo se fijaron las reglas.** Cada regla sigue la convención que ya era mayoritaria en el corpus, o un criterio clínico explícito. No se eligieron para que coincidan con lo que predice el modelo. El análisis de errores solo miró `dev`. Las reglas se aplican igual a `dev` y a `test`, sin mirar ningún resultado del sistema sobre `test`.

## El principio: la prueba de la mención mínima

> Se quita una palabra del borde de la mención **solo si lo que queda sigue siendo el mismo hallazgo**.

- «muy confundido» → `confundido`: sigue siendo confusión.
- «orina mucho» → se queda `orina mucho`: «orina» sola no es un hallazgo, es la poliuria la que lo hace.
- «respira muy de vez en cuando» → se queda entero: sin la frecuencia no hay bradipnea.

El detalle que se pierde (la intensidad, el tiempo, el desencadenante) **va en `normalized`**, no en el span. Por ejemplo, `me mareo` en «me mareo cuando me paro» se normaliza como «mareo ortostático».

La mención sigue siendo **literal y continua**. Si una palabra que sobra queda en medio, como en «golpe fuerte en la cabeza», se deja.

## Reglas

Cada regla lleva el mismo identificador que la lista de casos a revisar.

### L1 · Intensidad y gravedad fuera

Se quitan del borde los intensificadores («muy», «mucho», «muchísimo», «bastante», «un poco», «poquito») y los grados de gravedad («leve», «fuerte», «intenso», «marcada», «severa», «grado I»).

| Sí | No |
| :--- | :--- |
| `confundido` | `muy confundido` |
| `dolor de cabeza` | `dolor de cabeza muy fuerte` |
| `esguince de tobillo` | `esguince de tobillo grado I` |
| `orina mucho` (excepción: «orina» sola no es un hallazgo) | `orina` |

La gravedad no se pierde para el triaje: el protocolo la lee del texto completo, y `normalized` puede recogerla («cefalea intensa»).

### L2 · Sin artículo indefinido inicial

Se quitan «un», «una», «unos» y «unas» al principio. Los artículos definidos que acompañan a una parte del cuerpo se mantienen, porque forman parte de cómo se describe el signo: `la boca seca`, `los ojos rojos`.

| Sí | No |
| :--- | :--- |
| `lunar`, `manchitas en la cara`, `herida que sangra` | `un lunar`, `unas manchitas en la cara` |
| `la boca seca` | `boca seca` |

«un poco de pastillas» no es un artículo más un hallazgo: no se toca.

### L3 · Sin verbos de marco

Fuera los verbos que solo introducen el hallazgo: «está», «tiene», «sigue», «se está poniendo», «siento que», «le salió». Se mantienen los verbos que **son** el síntoma: `me duele`, `me mareo`, `le arde al orinar`, `veo borroso`, `tiene que pujar`, `se le ve la cabeza del bebé` (sin «se le ve» no hay hallazgo).

| Sí | No |
| :--- | :--- |
| `hinchada`, `morado`, `azulito`, `dormido` | `está hinchada`, `se está poniendo azulito`, `sigue muy dormido` |
| `me voy a morir` | `Siento que me voy a morir` |

### L4 · Instrumento y circunstancia fuera; características dentro

En lesiones, se quita el instrumento o la circunstancia: «con un vidrio», «con la puerta», «con aceite hirviendo», «pelando una papa», «jugando fútbol». Se mantiene lo que nombra el tipo de lesión (`Herida por arma blanca`) y lo que cambia el hallazgo (`vómito con sangre`, `tos con flema verde`, `sangrado vaginal abundante con coágulos`).

| Sí | No |
| :--- | :--- |
| `Me corté la muñeca` | `Me corté la muñeca con un vidrio` |
| `Quemadura` | `Quemadura con aceite hirviendo en toda la pierna` |
| `vómito con sangre` | `vómito` |
| `se atoró con un pedazo de comida` (la circunstancia es la condición) | `se atoró` |

### L5 · Tiempo, número de veces y desencadenante fuera

Se quitan «desde…», «hace…», «cuando…», «cinco veces», «ayer». Se mantiene la frecuencia cuando define el hallazgo: `orinando a cada rato` (polaquiuria) o `respira muy de vez en cuando` (bradipnea).

| Sí | No |
| :--- | :--- |
| `vomitó`, `no he orinado`, `me mareo` | `vomitó cinco veces`, `no he orinado desde la mañana`, `me mareo cuando me paro` |
| `ganas de orinar a cada rato` | `ganas de orinar` |

### L6 · Gestación con su edad gestacional

La gestación se anota siempre como `diagnoses`, con la edad gestacional si se dice, porque el protocolo la usa: `embarazada de 34 semanas`, `Gestante de 34 semanas`, `siete meses de embarazo`. Si no hay edad, `embarazada` o `Gestante`.

### L7 · Hallazgos normales como hallazgos negados

Es la regla de negación de la guía de anotación («respiro bien» niega la disnea), aplicada sin excepciones. Un hallazgo normal **de una función o un signo concreto** se anota en `symptoms` con `negated: true`, y `normalized` lleva el hallazgo que niega:

| Mención | `normalized` |
| :--- | :--- |
| `consciente` | inconsciencia |
| `saturación normal` | hipoxemia |
| `marcha conservada` | alteración de la marcha |
| `comiendo bien` | hiporexia |

No se anotan las afirmaciones genéricas de salud («sano», «previamente sano», «sin antecedentes»), porque no niegan un hallazgo concreto. Tampoco las segundas menciones que solo califican un hallazgo ya anotado («el dolor es como un 3 de 10»): **cada hallazgo se anota una vez**, en su primera mención.

### L8 · El evento traumático se anota

**Este es un cambio de criterio.** La guía anterior decía que el mecanismo no se anota, pero el corpus ya anotaba muchos eventos (`caída`, `Se cayó del andamio`, `Lo atropelló una buseta`, `accidente en moto`). Además, el protocolo usa la energía del mecanismo para clasificar. Con la regla nueva:

- El **evento** se anota en `diagnoses`, con su medio o su altura, porque miden la energía: `Se cayó de la bicicleta`, `Me caí de la escalera`, `Atropellado por un bus`, `accidente de moto`, `choque`.
- La **lesión**, si se nombra, se anota aparte: `fracturas en ambas piernas`.
- La **circunstancia** no se anota (L4): «jugando fútbol».

### L9 · Signo observable o nombre de enfermedad

- **`symptoms`:** lo que el paciente siente o lo que se observa, aunque sugiera un diagnóstico: `ampollas`, `caspa`, `la muñeca me quedó chueca` (deformidad), `signos de deshidratación`.
- **`diagnoses`:** lo que tiene nombre de enfermedad, lesión o síndrome, aunque sea coloquial: `gripa`, `agripado`, `nacido en la axila`, `deshidratación`, `cólico renal izquierdo`.
- **`history`:** igual que antes. Los antecedentes crónicos o previos.

## Lo que no cambia

- El span es **literal**, con los errores de transcripción.
- La partícula de negación **no** entra en la mención («no tiene dolor en el pecho» → `dolor en el pecho`, `negated: true`). La excepción sigue siendo la misma: frases como «no responde» o «no puede mover el brazo», que describen un hallazgo presente.
- Si un hallazgo afecta a varias partes del cuerpo coordinadas, es una sola mención: `quemado el pecho, los brazos y la cara`. Si son hallazgos distintos, van por separado cuando cada uno se puede marcar como texto continuo.
- Las alergias llevan `farmaco` (ver la guía de anotación).

## Cómo hacer la revisión

1. **Aprobar esta guía** con el clínico antes de tocar el corpus. Una vez aprobada, no se cambia según los resultados.
2. **Generar la lista de casos:**

   ```bash
   python ml/ner/revision_corpus.py
   ```

   Escribe [`revision/casos_a_revisar.md`](revision/casos_a_revisar.md), con una propuesta por regla y por caso, en `dev` y en `test`. Son **avisos**: algunos serán falsas alarmas (por ejemplo, `orina mucho` se queda como está).
3. **Corregir `corpus_entidades.json`** caso por caso con las mismas reglas en los dos splits. El caso pasa a `"estado": "revisado"`. Si cambia el texto de una mención, revisa también `normalized`.
4. **Validar** con `pytest backend/triage/tests/test_entity_corpus.py` y volver a generar la lista. Al final solo deben quedar falsas alarmas.
5. **Doble anotación.** El segundo anotador etiqueta a ciegas los 30 casos de `doble_anotacion/` con esta misma guía, y se calcula el acuerdo. Ese acuerdo es el techo realista de cualquier sistema y se reporta en la tesis.
6. **Reentrenar** con una corrida corta en Colab (`REUSE_STAGE1 = True`, unos 20 minutos). Solo después se evalúa `test`, **una vez** (paso 4.1).

**Lo que no se hace:**
- Mirar las predicciones de ningún motor sobre `test` para decidir cómo anotarlo.
- Cambiar una regla después de ver una cifra.
- Corregir solo `dev`: las reglas se aplican igual a todo el corpus.
