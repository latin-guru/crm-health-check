# Guía de uso de CRM Health Check

*[Read in English](runbook.md)*

Una guía práctica para el gerente de ventas o de mercadeo que responde por la calidad de los datos del CRM. Explica qué muestra el informe, cómo leerlo y cómo trabajar las listas de correcciones cada semana.

> Todo en este repositorio usa **Bayline Loop**, una empresa ficticia, con datos generados. Las cifras del informe son datos de muestra.

## 1. Qué preguntas responde el informe

| Pregunta | Página |
|---|---|
| ¿Podemos confiar en el CRM hoy? | **Overview**: puntaje de salud por objeto, problemas por gravedad y las 5 correcciones más importantes |
| ¿Qué está mal exactamente y por qué importa? | **Data Health**: una sección por cada revisión, con los registros afectados |
| ¿Qué corrijo y quién lo corrige? | **Fix List**: tres archivos CSV, uno por tipo de corrección |
| ¿Qué hay en el pipeline y qué se va a cerrar? | **Pipeline & Forecast** |
| ¿Qué fuentes de mercadeo traen los negocios ganados? | **Attribution** |
| ¿Por qué nuestro ARR no cuadra con lo que factura finanzas? | **Reconciliation** |
| ¿Cómo se define cada cifra? | **Methodology**, con enlace al SQL que la calcula |

## 2. Rutina semanal (unos 30 minutos)

1. **Corra la auditoría** sobre la exportación más reciente. `chc generate` es solo para la demostración; con exportaciones reales, ponga los archivos CSV en `data/` y ejecute `chc build`.
2. **Abra el Overview.** Anote los tres puntajes de salud y compárelos con los de la semana pasada. Si un puntaje baja, están entrando datos malos nuevos: busque la causa (un formulario, una integración, un vendedor nuevo) en vez de solo limpiar.
3. **Trabaje las 5 correcciones principales** en orden. Primero las de gravedad alta, porque son las que dañan las cifras de ingresos.
4. **Importe `fixes.csv`** (sección 4).
5. **Envíe `merge_candidates.csv`** a la persona encargada de fusionar registros (sección 5).
6. **Envíe `needs_owner_review.csv`** a cada responsable, filtrado solo con sus registros (sección 6).
7. **Revise Reconciliation** y pase a finanzas o al dueño del negocio cada cuenta que no esté en Matched (sección 7).

## 3. Cómo leer las revisiones

| ID | Revisión | Por qué importa | Quién la corrige |
|---|---|---|---|
| H01 | Contactos duplicados | El historial de una persona queda partido y la contactan dos veces | Encargado de fusiones (con revisión) |
| H02 | Empresas duplicadas | Los ingresos y contactos de una cuenta quedan repartidos entre copias | Encargado de fusiones (con revisión) |
| H03 | Correo faltante o inválido | Al contacto no se le puede escribir, ni se puede deduplicar ni atribuir | Responsable del registro |
| H04 | Etapa del ciclo de vida faltante o incorrecta | El embudo y el conteo de clientes quedan mal | Etapas en blanco: automático. "Customer" sin negocio ganado: responsable del registro |
| H05 | Negocio sin empresa o sin contacto | El negocio no suma en los ingresos de la cuenta ni en la atribución | Dueño del negocio |
| H06 | Negocio abierto estancado | El pipeline y el pronóstico incluyen plata que no va a llegar | Dueño del negocio: actualizarlo o cerrarlo |
| H07 | Negocio ganado incompleto | Los informes de ingresos no lo cuentan y el CRM no cuadra con facturación | Dueño del negocio, con base en la orden de compra firmada |
| H08 | Responsable inactivo o faltante | Nadie le hace seguimiento | Contactos y negocios: automático. Empresas: gerente de ventas |
| H09 | Valor de UTM no estándar | Un mismo canal aparece con varios nombres y queda subcontado | Alias conocidos: automático. Valores desconocidos: operaciones de mercadeo |

Gravedad: **alta** daña las cifras de ingresos o los informes, **media** daña el seguimiento o la asignación, **baja** daña el detalle de la atribución.

## 4. Cómo importar `fixes.csv`

`fixes.csv` solo trae cambios que una regla puede hacer con seguridad: llenar una etapa del ciclo de vida en blanco a partir de los negocios de la empresa, pasar un registro de un responsable que ya no está al responsable activo de la empresa, y reescribir un alias de UTM con su valor estándar.

El archivo tiene cuatro columnas: `Record ID`, `Object`, `Property`, `New Value`. HubSpot importa un objeto a la vez y espera una columna por propiedad, así que:

1. Filtre el archivo por un solo **Object** y una sola **Property** (por ejemplo, contact + `utm_source`).
2. Cambie el nombre de la columna `New Value` por el nombre de la propiedad.
3. En HubSpot, importe el archivo como actualización de registros existentes de ese objeto, cruzando por **Record ID**.
4. Repita con el siguiente par de objeto y propiedad.
5. Vuelva a correr la auditoría. Esos problemas ya no deberían aparecer.

Antes de cada importación, revise unas cuantas filas a mano. Una regla es tan buena como los datos que lee.

## 5. Cómo trabajar las fusiones (`merge_candidates.csv`)

Las fusiones **nunca son automáticas**. Una fusión en HubSpot junta el historial de dos registros y no se puede deshacer por completo; una fusión equivocada asocia negocios y correos al cliente equivocado.

En cada fila, abra los dos registros (`duplicate_record_id` y `keep_record_id`) y confirme que de verdad son la misma persona o la misma empresa:

- **Contactos:** la misma persona, no un buzón compartido de un equipo.
- **Empresas:** el mismo negocio, no una marca hermana ni una filial que comparte el dominio.

Si coinciden, fusione el duplicado en el registro que se conserva (el más antiguo). Si no, deje los dos y anote por qué, para que ese par no se vuelva a revisar.

## 6. Revisiones del responsable (`needs_owner_review.csv`)

Aquí va todo lo que necesita el criterio de una persona: correos faltantes o dañados, contactos marcados como "customer" sin negocio ganado, negocios sin asociaciones o sin valor, negocios estancados, empresas a nombre de alguien que ya se fue y valores de UTM desconocidos. Filtre por responsable y envíele a cada persona sus filas. Pida las correcciones para la siguiente revisión semanal.

En los negocios estancados (H06), el responsable define un próximo paso real con una nueva fecha de cierre, o cierra el negocio como perdido. Correr la fecha de cierre sin un próximo paso solo esconde el problema.

## 7. Seguimiento de la conciliación

Cada cuenta que no esté en **Matched** tiene una explicación de una frase. Pasos típicos:

| Categoría | Qué hacer |
|---|---|
| CRM-only | Pregúntele a finanzas si al cliente se le factura con otro dominio; si se retiró, regístrelo en el CRM |
| Billing-only | Cree o ubique la empresa y registre el negocio ganado, o confirme que fue una inscripción por autoservicio |
| Amount mismatch | Compare la orden de compra firmada con la suscripción: descuento, una tienda adicional, cambio de precio o un valor faltante (H07) |
| Term mismatch | Corrija el lado donde un valor mensual quedó escrito como anual (o al revés) |
| Currency mismatch | Acuerde la moneda del contrato y corrija el otro sistema |

Tenga presente que el ARR aquí es valor recurrente contratado. No es el ingreso que reconoce finanzas, así que es normal ver pequeñas diferencias por fechas.

## 8. Definiciones

- **Puntaje de salud:** porcentaje de registros de un objeto (contactos, empresas, negocios) sin ningún problema en ninguna revisión.
- **Pronóstico ponderado:** suma del valor de cada negocio abierto multiplicado por la probabilidad de su etapa (vea `config/pipeline.yml`). Solo es confiable si las etapas están al día, y por eso importa H06.
- **Primer toque / último toque:** la fuente del primer / último toque de mercadeo registrado del contacto principal de un negocio ganado, antes de que se creara el negocio.
- **Dominio normalizado:** en minúsculas, sin `http(s)://`, sin `www.` y sin ruta. Se usa para cruzar facturación con el CRM, porque los dos sistemas no comparten un ID.
