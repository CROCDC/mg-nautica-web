# WhatsApp Business — cómo obtener las credenciales

Esta integración hace que los barcos aparezcan como **productos** dentro del chat de WhatsApp Business — los clientes los pueden ver y consultar como si fuera una tienda. **No envía mensajes automáticos** (esa es otra integración distinta).

> Tiempo estimado: 15–20 minutos. Reusa todo lo que hiciste en la guía de Facebook.
>
> **Solo desde computadora** (excepto un paso opcional al final que se hace en la app del celular).

## Lo que vamos a obtener

1. **Catalog ID** (un número largo)
2. **Access Token** — **el mismo token permanente del Facebook** (no hay que generar otro)

---

## Antes de empezar

Necesitás:

- Tener instalada la app **WhatsApp Business** en el celular (no la app personal de WhatsApp). El número de teléfono debe ser el de MG Náutica.
- Haber completado la guía de Facebook ([facebook.md](facebook.md)) — Business Manager, app de Meta, System User y token permanente.

## Paso 1 — Vincular WhatsApp Business al Business Manager

1. Entrá a https://business.facebook.com con la cuenta admin (la misma que usaste en Facebook).
2. Ícono de engranaje (⚙) → **Configuración del negocio**.
3. Menú izquierdo: **"Cuentas"** → **"Cuentas de WhatsApp"**.
4. Click **"Agregar"** (botón azul).
5. Seguí el flujo:
   - Vincular un número → ingresá el número de teléfono de MG Náutica (el que tiene WhatsApp Business).
   - Recibís un código por SMS o llamada → ingresalo.
   - Confirmar.

## Paso 2 — Crear el catálogo en Commerce Manager

Aún no tenemos un catálogo de productos. Vamos a crear uno.

1. En Business Manager, abrí el menú **☰** arriba a la izquierda.
2. Buscá **"Commerce Manager"**, o entrá directo a https://business.facebook.com/commerce/
3. Click **"Comenzar"** o **"Agregar catálogo"** (botón azul).
4. **Tipo de catálogo**: elegí **"E-commerce"** (productos generales).
5. **Configurar catálogo**:
   - **Subir productos**: marcá **"Agregar productos manualmente"** (después la integración los crea sola).
   - **Propietario del catálogo**: tu Business Manager (sale por default).
   - **Nombre del catálogo**: `MG Náutica - Embarcaciones`.
6. **"Crear catálogo"**.

## Paso 3 — Vincular el catálogo a WhatsApp Business

1. Una vez creado el catálogo, click en **"Configuración"** dentro del catálogo (menú izquierdo).
2. Buscá **"Recursos vinculados"** o **"Connected assets"** (a veces aparece como "Conexiones").
3. **"Agregar recurso"** → **"Cuenta de WhatsApp Business"**.
4. Seleccioná la cuenta WhatsApp del paso 1.
5. Aceptá los términos de comercio que muestra Meta.

## Paso 4 — Asignar el catálogo al System User

Para que el token permanente del Facebook sirva también para tocar el catálogo, hay que asignar el catálogo al System User.

1. Volvé a **Configuración del negocio** (https://business.facebook.com/settings).
2. Menú izquierdo: **"Usuarios"** → **"Usuarios del sistema"**.
3. Click en `MG Nautica Backend` (el System User de la guía de Facebook).
4. **"Asignar recursos"** → buscá la sección **"Catálogos"** (puede estar dentro de "Fuentes de datos").
5. Seleccioná **MG Náutica - Embarcaciones**.
6. **Permisos**: activá **"Administrar catálogo"** (Manage Catalog).
7. **"Asignar"**.

## Paso 5 — Obtener el Catalog ID

1. En Commerce Manager, abrí el catálogo de MG Náutica.
2. Mirá la URL en la barra del navegador. Es algo así:
   ```
   https://business.facebook.com/commerce/catalogs/1234567890/home/
   ```
3. El número (`1234567890`) es tu **Catalog ID**. Copialo.

> Otra forma: Configuración del negocio → **"Cuentas"** → **"Catálogos"** → click en el catálogo → el ID aparece en la pantalla.

## Paso 6 — Verificar que el token tiene permisos de catálogo

Si en la guía de Facebook marcaste el permiso `catalog_management` en el paso 8 (estaba en la lista), el token ya sirve para WhatsApp Catalog. **No hay que generar uno nuevo.**

Si te olvidaste de marcarlo:

1. Configuración del negocio → Usuarios del sistema → click en `MG Nautica Backend`.
2. **"Generar nuevo token"**.
3. App: `MG Nautica Integraciones`. Caducidad: **"Nunca"**.
4. Marcá los **8 permisos** de la lista de la guía de Facebook, incluyendo `catalog_management`.
5. Generar y copiar el token nuevo.
6. Pasale al equipo técnico el token nuevo para que actualice las tres integraciones a la vez.

## Paso 7 — (Opcional) Mostrar el catálogo en el chat de WhatsApp móvil

Para que el catálogo aparezca como ícono dentro del chat de WhatsApp Business, hay que activarlo en la app:

1. App WhatsApp Business → **⋮** (tres puntitos arriba a la derecha) → **Herramientas para empresas** → **Catálogo**.
2. Si te pregunta entre "Catálogo local" y "Catálogo de Meta": elegí **"Catálogo de Meta"** (o "Vincular catálogo").
3. Seleccioná el catálogo que creaste en el paso 2.
4. Confirmar.

> Si no tenés esta opción, esperá unos minutos y volvé a entrar — Meta tarda en sincronizar después del paso 3.

---

## Lo que tenés que entregar al equipo técnico

```
WHATSAPP_CATALOG_ID = (el número del paso 5)
WHATSAPP_ACCESS_TOKEN = (el mismo valor que FACEBOOK_PAGE_ACCESS_TOKEN)
```

---

## Mantenimiento futuro

- El token no caduca mientras el System User exista y el catálogo esté asignado.
- **No borres el catálogo** desde Commerce Manager. Si lo borrás, todos los productos se pierden y hay que rehacer la integración.
- Cuando los barcos se venden, el equipo técnico los marca como vendidos en el admin y la integración los **quita automáticamente** del catálogo de WhatsApp.

---

## Recomendación: verificación de empresa en Meta

Para usar todas las funciones del catálogo en producción, conviene **verificar la empresa** en Meta Business Manager. No es estrictamente obligatorio para empezar, pero te quita límites y da más confianza a los clientes. Documentos típicos que pide Meta:

- Constancia de inscripción fiscal (RUT en Uruguay, CUIT en Argentina).
- Acta constitutiva o estatuto social actualizado.
- DNI / Pasaporte del administrador principal de Business Manager.
- Factura de servicio público o extracto bancario que confirme la dirección.

Se hace desde Configuración del negocio → **Centro de seguridad** o **Información de la empresa** → **Verificación de empresa**. Tarda 1–5 días hábiles.

---

## Si algo no funciona

| Problema | Qué hacer |
|---|---|
| No me aparece "Catálogo de Meta" en la app de WhatsApp Business | El paso 3 no quedó bien. Volvé a Commerce Manager y verificá que el catálogo tenga la cuenta WhatsApp como recurso vinculado. |
| Los productos no aparecen en el chat | Esperá 30 minutos. Meta tarda en propagar. |
| Cambios de precio o descripción no se actualizan | El cache de WhatsApp puede tardar hasta 24h. Si después de 24h no actualiza, mandale la lista de productos al equipo técnico. |
| Meta dice que el catálogo "está en revisión" | Algunas categorías de productos requieren aprobación manual. Los barcos normalmente pasan sin problema. Esperá 24–48h. |
| Permission error al sincronizar el primer barco | Falta el permiso `catalog_management` en el token. Repetí el paso 6. |
| El número de WhatsApp del paso 1 no es el de MG Náutica | Pasá primero el número correcto a WhatsApp Business; si no, el catálogo se asocia al número equivocado. |

---

## Fuentes

- [Meta — Conectar y activar tu catálogo en Meta para WhatsApp](https://help.chatecommerce.com/conectar-activar-catalogo-meta-whatsapp/)
- [Meta — Cómo crear un catálogo en Meta Business Manager](https://www.tiendanube.com/blog/catalogo-de-facebook/)
- [WhatsApp Business — Acerca del catálogo](https://faq.whatsapp.com/405903568419894)
- [Meta — Verificar tu negocio en Meta Business Suite](https://es-la.facebook.com/business/help/2058515294227817)
