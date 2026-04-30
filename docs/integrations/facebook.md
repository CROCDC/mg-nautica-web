# Facebook — cómo obtener las credenciales

Esta es la guía base para Facebook, Instagram y WhatsApp Catalog. Hacé esta primero — al terminarla, las otras dos se hacen mucho más rápido.

> Tiempo estimado: 30–40 minutos. Necesitás ser **administrador** de la página de Facebook de MG Náutica.
>
> **Solo desde computadora** (la app de celular no tiene varias de las pantallas que vamos a usar).

## Lo que vamos a obtener

Al final vas a entregar al equipo técnico:

1. **Page ID** (un número largo de la página)
2. **Access Token permanente** (una clave que no caduca nunca)

---

## Paso 1 — Verificar que tenés una página de Facebook

MG Náutica tiene que tener una **Página** de Facebook (con botón "Seguir" / "Me gusta"), NO un perfil personal (con botón "Agregar como amigo").

1. Abrí la página de MG Náutica en Facebook desde tu computadora.
2. Si arriba dice "Me gusta" o "Seguir" → es **página** ✅, continuá al paso 2.
3. Si dice "Agregar como amigo" → es **perfil personal**. Avisale al equipo técnico que hay que crear una página primero.

## Paso 2 — Encontrar el Page ID

1. En la página de MG Náutica → menú izquierdo (debajo de la foto de portada) → click en **"Acerca de"**.
2. Bajá hasta el final hasta el bloque **"Transparencia de la página"**.
3. Ahí aparece **"ID de la página"** seguido de un número largo (ej: `100072345678901`).
4. Copialo. Ese es tu **Page ID**.

> Si no aparece la sección "Transparencia de la página", la página puede ser muy nueva. Esperá 24h o pedile al equipo técnico que lo busque.

## Paso 3 — Crear (o entrar a) Meta Business Manager

Meta Business Manager es la "central administrativa" de Facebook/Instagram/WhatsApp. Si MG Náutica ya tiene uno, saltá al paso 4.

1. Entrá a https://business.facebook.com
2. Si pregunta **"¿Querés crear una cuenta de empresa?"**, click en **"Crear cuenta"**.
3. Completá:
   - **Nombre de la empresa**: `MG Náutica`
   - **Tu nombre**: tu nombre real (admin)
   - **Email del trabajo**: tu email
4. Confirmá con el email de verificación que te llega.

## Paso 4 — Vincular la página al Business Manager

1. En Business Manager: ícono de engranaje (⚙) arriba a la derecha → te lleva a **"Configuración del negocio"**.
2. En el menú izquierdo: **"Cuentas"** → **"Páginas"**.
3. Botón **"Agregar"** → **"Agregar una página"**.
4. Buscá "MG Náutica" → seleccionala → **"Agregar página"**.
5. Confirmar.

## Paso 5 — Crear una "App" de Meta

Esta es una "aplicación" técnica que sirve de puente entre el sistema de MG Náutica y Facebook. Es un trámite obligatorio que hacés una sola vez.

1. Entrá a https://developers.facebook.com/apps
2. Click en **"Crear app"** (botón verde arriba a la derecha).
3. Te pregunta **"¿Qué tipo de app querés crear?"** → elegí **"Empresa"** (Business).
4. Completá:
   - **Nombre de la app**: `MG Nautica Integraciones`
   - **Email de contacto**: tu email
   - **Cuenta de empresa**: seleccioná el Business Manager del paso 3
5. Click en **"Crear app"**.
6. Te pueden pedir tu contraseña de Facebook para confirmar.

> Una vez creada, en el panel de la app, anotá el **App ID** (el número grande arriba). Lo vas a necesitar en el paso 7.

## Paso 6 — Crear un "System User" (usuario de servicio)

Un System User es un usuario "de servicio" que existe solo dentro de Business Manager — no es una persona real, no se loguea, no cambia contraseña. Es el método **recomendado por Meta** para tokens permanentes porque no depende de un usuario humano.

1. Volvé a https://business.facebook.com/settings (Configuración del negocio).
2. En el menú izquierdo, bajá hasta **"Usuarios"** → **"Usuarios del sistema"**.
3. Click **"Agregar"** (botón azul).
4. Si te aparece un cartel de "Términos", aceptalo.
5. Completá:
   - **Nombre**: `MG Nautica Backend`
   - **Función**: **Administrador**
6. **"Crear usuario del sistema"**.

## Paso 7 — Asignar permisos al System User

El System User existe pero todavía no tiene acceso a nada. Vamos a darle acceso a la página y a la app.

### 7a — Asignar la página

1. En la pantalla del System User recién creado, click en **"Asignar recursos"** o **"Add Assets"**.
2. Tipo de recurso: **"Páginas"**.
3. Seleccioná la página de MG Náutica.
4. **Permisos**: activá el toggle **"Administrar página"** (Manage Page) — incluye crear contenido, gestionar, etc.
5. **"Asignar"**.

### 7b — Asignar la app

1. Volvé a la pantalla del System User → **"Asignar recursos"** otra vez.
2. Tipo de recurso: **"Apps"**.
3. Seleccioná `MG Nautica Integraciones` (la app del paso 5).
4. **Permisos**: activá **"Administrar app"** (Manage app).
5. **"Asignar"**.

## Paso 8 — Generar el token permanente

1. Seguí en la pantalla del System User.
2. Click en **"Generar nuevo token"** (Generate new token).
3. En el popup:
   - **App**: seleccioná `MG Nautica Integraciones`.
   - **Caducidad del token**: elegí **"Nunca"** (Never). ⚠️ Si dejás "60 días", el token vence en 60 días.
   - **Permisos**: marcá los siguientes (todos):
     - `pages_show_list`
     - `pages_manage_posts`
     - `pages_read_engagement`
     - `pages_manage_metadata`
     - `business_management`
     - `instagram_basic`
     - `instagram_content_publish`
     - `catalog_management`
4. Click **"Generar token"**.
5. Meta muestra el token **una sola vez en pantalla**. Es una clave larga que empieza con `EAAG...`.
6. **Copiala completa** y pegala en un Bloc de Notas. Si cerrás la ventana sin copiarla, **tenés que generar otra** — Meta no te la vuelve a mostrar.

> Marcamos los permisos de Instagram y WhatsApp también acá para no tener que regenerar el token después. El mismo token va a servir para las tres integraciones.

---

## Lo que tenés que entregar al equipo técnico

```
FACEBOOK_PAGE_ID = (el número del paso 2)
FACEBOOK_PAGE_ACCESS_TOKEN = (la clave permanente del paso 8)
```

> Pasá el `FACEBOOK_PAGE_ACCESS_TOKEN` por un canal seguro (1Password / gestor de credenciales). **Es como una contraseña.** Cualquiera con esa clave puede publicar en la página.

---

## Mantenimiento futuro

- El token **no caduca por tiempo**. Va a seguir funcionando indefinidamente.
- Se rompe si:
  - Borrás el System User desde Business Manager.
  - Borrás la app de Meta del paso 5.
  - Quitás la página o la app de los recursos asignados al System User.
- Si se rompe, repetí el paso 8 (los pasos 1–7 ya quedan listos).
- **No depende de tu cuenta personal** — si te vas de la empresa, el System User sigue existiendo y otra persona puede regenerar el token desde Business Manager.

---

## Si algo no funciona

| Problema | Qué hacer |
|---|---|
| No me aparece "Usuarios del sistema" en el menú | Tu Business Manager no está completo. Volvé a Configuración del negocio → completá la información de la empresa (Información comercial). |
| Al generar el token no veo la opción "Nunca" | Probablemente la app del paso 5 todavía no está asignada al System User (paso 7b). Volvé y asignala. |
| Generé el token pero no lo copié | Volvé a Usuarios del sistema → click en el System User → "Generar nuevo token" otra vez. Meta no recupera el viejo, te genera uno nuevo. |
| El equipo técnico dice que faltan permisos | Volvé al paso 8 y verificá que estén marcados los **8 permisos** de la lista. Si te falta alguno, generá un token nuevo. |
| No me deja agregar la página al System User | Tu rol en la página es "Editor" o menor. Pediselo a un admin de la página o pedí que te promuevan. |

---

## Fuentes

- [Meta — Cómo crear Facebook Business Manager (paso a paso)](https://es-la.facebook.com/business/help/2058515294227817)
- [Meta — Install Apps, Generate, Refresh, and Revoke Tokens](https://developers.facebook.com/docs/business-management-apis/system-users/install-apps-and-generate-tokens/)
- [Meta — Find your Facebook Page ID](https://www.facebook.com/help/1503421039731588)
- [Meta — Obtaining a System User Access Token](https://support.infosum.com/hc/en-us/articles/21987155916306-Obtaining-a-System-User-Access-Token-in-Meta)
