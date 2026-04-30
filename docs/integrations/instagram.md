# Instagram — cómo obtener las credenciales

Esta guía es **muy corta porque reusa todo lo que generaste en la guía de Facebook** ([facebook.md](facebook.md)).

> Tiempo estimado: 10 minutos.
>
> **Solo desde computadora.**

## Lo que vamos a obtener

1. **Instagram Business Account ID** (un número largo de ~17 dígitos)
2. **Access Token de Instagram** — **el mismo token permanente del Facebook** (no hay que generar otro)

---

## Paso 1 — Convertir Instagram a "Cuenta de empresa"

Si la cuenta de Instagram de MG Náutica todavía no es una cuenta de empresa, hay que cambiarla. Es gratis y reversible. Esto se hace **desde el celular** porque es la única pantalla donde existe la opción (después volvemos a la computadora).

1. Abrí la app de Instagram con la cuenta de MG Náutica.
2. Tu perfil → menú (☰ arriba a la derecha) → **"Configuración y privacidad"**.
3. Buscá **"Tipo de cuenta y herramientas"** → **"Cambiar a cuenta profesional"**.
4. **Elegí una categoría**: "Concesionario de embarcaciones", "Empresa local", o cualquier opción de negocios.
5. Cuando pregunta **"¿Empresa o creador?"** → elegí **"Empresa"**.
   - ⚠️ NO elegir "Creador". Con creator no funciona la publicación automática.
6. Confirmá.

> Visualmente la cuenta no cambia (el nombre, las fotos, los seguidores siguen igual). Solo se habilita el modo profesional internamente.

## Paso 2 — Vincular Instagram a la página de Facebook

Sin este vínculo, la integración no puede publicar.

1. Desde la computadora, entrá a https://business.facebook.com
2. Ícono de engranaje (⚙) → **Configuración del negocio**.
3. En el menú izquierdo: **"Cuentas"** → **"Cuentas de Instagram"**.
4. Click **"Agregar"** (botón azul).
5. Iniciá sesión con la cuenta de Instagram de MG Náutica (en la ventana popup).
6. Cuando pregunte "¿A qué página de Facebook querés vincularla?" → seleccioná la página de MG Náutica.
7. Confirmar.

## Paso 3 — Asignar Instagram al System User

Para que el token permanente del Facebook sirva también para Instagram, hay que asignar la cuenta IG al System User que creaste.

1. Seguí en **Configuración del negocio**.
2. Menú izquierdo: **"Usuarios"** → **"Usuarios del sistema"**.
3. Click en `MG Nautica Backend` (el System User de la guía de Facebook).
4. **"Asignar recursos"** → **"Cuentas de Instagram"**.
5. Seleccioná la cuenta de Instagram de MG Náutica.
6. **Permisos**: activá **"Crear contenido"** (Create Content) y **"Administrar"** (Manage).
7. **"Asignar"**.

## Paso 4 — Obtener el Instagram Business Account ID

1. Seguí en **Configuración del negocio**.
2. Menú izquierdo: **"Cuentas"** → **"Cuentas de Instagram"**.
3. Click en la cuenta de Instagram de MG Náutica que aparece en la lista.
4. En la pantalla que se abre, vas a ver un campo **"ID de Instagram"** o **"Account ID"** con un número largo de ~17 dígitos.
5. Copialo. Ese es tu **Instagram Business Account ID**.

> Si no encontrás el ID en esa pantalla, click en **"Ver más detalles"** o en los tres puntitos (⋯) al lado del nombre — el ID aparece ahí.

## Paso 5 — Verificar que el token de Facebook tiene permisos de Instagram

Si en la guía de Facebook marcaste los permisos `instagram_basic` e `instagram_content_publish` en el paso 8 (estaban en la lista), el token ya sirve para Instagram. **No hay que generar uno nuevo.**

Si por error te olvidaste de esos permisos:

1. Volvé a Configuración del negocio → Usuarios del sistema → click en `MG Nautica Backend`.
2. Click **"Generar nuevo token"**.
3. En el popup, seleccioná la app y caducidad **"Nunca"**.
4. Marcá los **8 permisos** que listamos en la guía de Facebook (incluyendo los dos de Instagram).
5. Generar y copiar el token nuevo.
6. Pasale al equipo técnico el token nuevo para que actualice las tres integraciones a la vez.

---

## Lo que tenés que entregar al equipo técnico

```
INSTAGRAM_BUSINESS_ACCOUNT_ID = (el número de ~17 dígitos del paso 4)
INSTAGRAM_ACCESS_TOKEN = (el mismo valor que FACEBOOK_PAGE_ACCESS_TOKEN)
```

Sí — los valores de `FACEBOOK_PAGE_ACCESS_TOKEN` e `INSTAGRAM_ACCESS_TOKEN` son **idénticos**. La misma clave sirve para las dos integraciones.

---

## Mantenimiento futuro

- Mismo que Facebook: el token no caduca mientras el System User exista y la app de Meta esté activa.
- Si Instagram **deja de aparecer vinculada a la página** (raro, pero pasa), repetí el paso 2.

---

## Si algo no funciona

| Problema | Qué hacer |
|---|---|
| El paso 4 no muestra ningún ID | El Instagram no está bien vinculado al Business Manager. Volvé al paso 2. |
| La cuenta de IG no me deja ser "Empresa", solo "Creador" | Revisá si la cuenta tiene activado un programa de monetización que bloquea el cambio. Configuración → Creador → desactivar. |
| Tengo dos cuentas de IG y no sé cuál vincular | Vinculá la que vas a usar para publicar avisos. Solo se puede vincular una por página de Facebook. |
| Cuando intentamos publicar dice "permission missing" | Faltan permisos de Instagram en el token. Hacé el paso 5 y regenerá el token. |

---

## Fuentes

- [Meta — Cambiar a cuenta profesional en Instagram](https://www.optimoclick.com/blog/como-cambiar-a-cuenta-profesional-en-instagram-paso-a-paso/)
- [Meta — Cómo conectar Instagram con Facebook](https://www.facebook.com/business/help/898752960195806)
- [Meta — Instagram Graph API access token](https://developers.facebook.com/docs/instagram-platform/reference/access_token/)
