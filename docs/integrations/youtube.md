# YouTube — cómo obtener las credenciales

Esta guía te explica cómo dar permiso a MG Náutica para actualizar el título y la descripción de los videos del canal automáticamente. Los videos se siguen subiendo a mano — la integración solo edita su información.

> Tiempo estimado: 30–40 minutos.
>
> **Solo desde computadora.**
>
> El último paso (generar el "Refresh Token") **lo hace el equipo técnico** — vos solo le pasás los dos valores de los pasos previos y autorizás con tu cuenta cuando te avisen.

## Lo que vamos a obtener

1. **Client ID** (un texto largo terminado en `.apps.googleusercontent.com`)
2. **Client Secret** (otra clave secreta)
3. **Refresh Token** ← **lo genera el equipo técnico** con tu autorización

---

## Paso 1 — Saber qué cuenta de Google administra el canal

1. Entrá a YouTube con la cuenta que sube los videos de MG Náutica.
2. Click en tu foto de perfil (arriba a la derecha) → **"Cambiar de cuenta"**.
3. Anotá qué email aparece como "principal" del canal de MG Náutica.

Esa cuenta de Google es la que tenés que usar en TODOS los pasos siguientes. Si te equivocás de cuenta, el sistema final va a poder editar otro canal, no el que querés.

## Paso 2 — Crear un proyecto en Google Cloud

Google necesita un "proyecto" técnico que sirve de contenedor para los permisos.

1. Entrá a https://console.cloud.google.com
2. Iniciá sesión con la cuenta del paso 1.
3. Si es tu primera vez, te puede pedir aceptar términos de servicio. Aceptalos.
4. Arriba a la izquierda, click en el dropdown que dice **"Seleccionar un proyecto"** → **"Proyecto nuevo"**.
5. Nombre del proyecto: `MG Nautica YouTube`.
6. Organización: dejala como está.
7. Click en **"Crear"**.
8. Esperá unos segundos a que se cree y seleccionalo.

## Paso 3 — Activar la API de YouTube

1. En el menú izquierdo (las tres rayas arriba a la izquierda), buscá **"APIs y servicios"** → **"Biblioteca"**.
2. En el buscador escribí: `YouTube Data API v3`.
3. Click en el resultado.
4. Botón azul **"Habilitar"**.

## Paso 4 — Configurar la "pantalla de consentimiento"

1. Menú izquierdo: **"APIs y servicios"** → **"Pantalla de consentimiento de OAuth"**.
2. Te pregunta **"User Type"** → elegí **"Externo"** → **"Crear"**.
3. Llenado de información:
   - **Nombre de la app**: `MG Nautica YouTube Sync`
   - **Email de asistencia**: tu email
   - **Logo**: opcional (subí el logo de MG Náutica si lo tenés en formato cuadrado)
   - **Dominio de la app**: `mgnautica.com`
   - **Email del desarrollador**: tu email
4. **"Guardar y continuar"**.

5. **Pantalla de scopes**: click **"Add or remove scopes"**.
   - En el buscador escribí: `youtube`
   - Marcá **`https://www.googleapis.com/auth/youtube`** (el que dice "Manage your YouTube account").
   - **"Update"** → **"Save and continue"**.

6. **Pantalla de Test users**: dejala vacía (vamos a publicar la app en el paso 5, no nos hace falta).
   - **"Save and continue"**.

7. **Resumen final** → **"Volver al panel"**.

## Paso 5 — IMPORTANTE: Publicar la app a Producción

Por defecto la app queda en modo **"Testing"** (prueba). En ese modo, el permiso que vamos a generar **se rompe a los 7 días**. Hay que pasarla a **"Producción"** para que el token dure indefinidamente.

1. En la pantalla de consentimiento de OAuth, vas a ver un cartel que dice **"Estado de publicación: Testing"**.
2. Click en el botón **"Publicar app"**.
3. Confirmar **"Confirm"**.
4. El estado cambia a **"En producción"** ✅.

> Google puede mostrar un cartel diciendo que tu app necesita "verificación" porque usa un permiso sensible (YouTube). **Ignoralo por ahora**. La app funciona igual sin verificación, solo que cuando autorices vas a ver un cartel de advertencia que vamos a saltar — es seguro porque la app la creaste vos mismo.

## Paso 6 — Crear las credenciales OAuth

1. Menú izquierdo: **"APIs y servicios"** → **"Credenciales"**.
2. Click **"Crear credenciales"** → **"ID de cliente de OAuth"**.
3. **Tipo de aplicación**: **"App de escritorio"**.
4. **Nombre**: `MG Nautica Backend`.
5. **"Crear"**.
6. Google muestra un popup con dos valores:
   - **ID de cliente** → copialo (termina en `.apps.googleusercontent.com`).
   - **Secreto del cliente** → copialo.
7. **"OK"**.

Estos dos valores son tu `YOUTUBE_CLIENT_ID` y `YOUTUBE_CLIENT_SECRET`. Pegalos en un Bloc de Notas para el final.

## Paso 7 — Pasale al equipo técnico para que genere el Refresh Token

El último paso (generar la clave permanente que la integración va a usar todos los días) lo hace el equipo técnico — vos solo autorizás con tu cuenta cuando te avisen.

1. Mandales:
   - El **Client ID** y **Client Secret** del paso 6.
   - El email de Google del paso 1.
2. Ellos te van a responder con un **link de autorización** (algo como `https://accounts.google.com/o/oauth2/...`).
3. Abrí ese link **logueado con la cuenta de Google del paso 1**.
4. Te aparece un cartel **"Google no ha verificado esta aplicación"** → click en **"Avanzado"** → **"Ir a MG Nautica YouTube Sync (no seguro)"**.
   - ⚠️ Es seguro, es la app que creaste vos en los pasos anteriores. Google muestra el warning porque no pasó verificación oficial — para uso interno (solo nuestra cuenta) no hace falta.
5. Aceptá los permisos: "Administrar tu cuenta de YouTube".
6. Te redirige a una página con un mensaje de éxito o un código.
7. Avisale al equipo técnico que ya autorizaste — el resto lo hacen ellos en el servidor.

> No tenés que copiar ni pegar nada en este paso. Después de hacer click en "Permitir", el sistema se encarga del resto.

---

## Lo que tenés que entregar al equipo técnico

```
YOUTUBE_CLIENT_ID = (el del paso 6, termina en .apps.googleusercontent.com)
YOUTUBE_CLIENT_SECRET = (el del paso 6)
Email de Google que administra el canal (paso 1)
```

> Pasá estos valores por canal seguro (1Password / gestor de credenciales). **Cualquiera con ellos puede editar tu canal.**

El **Refresh Token** lo genera el equipo técnico — no se lo entregás vos.

---

## Mantenimiento futuro

- El **Refresh Token no caduca por tiempo** mientras:
  - La app siga "En producción" (paso 5). NO la pongas en Testing nunca.
  - La integración haga al menos un sync cada 6 meses (la integración lo hace automáticamente, así que en la práctica nunca expira).
- Se rompe si:
  - Cambiás la contraseña de Google de la cuenta del paso 1.
  - Borrás el proyecto de Google Cloud.
  - Revocás manualmente el acceso de la app desde https://myaccount.google.com/permissions
- Si se rompe, el equipo técnico te manda otro link de autorización (paso 7) — no hace falta rehacer 1–6.

---

## Cómo cargar el ID de cada video en MG Náutica

Para cada barco que tenga video en YouTube:

1. Abrí el video en YouTube.
2. La URL es algo como:
   - `https://www.youtube.com/watch?v=ABC123XYZ` → el ID es `ABC123XYZ`
   - `https://www.youtube.com/shorts/ABC123XYZ` → el ID es `ABC123XYZ`
   - `https://youtu.be/ABC123XYZ` → el ID es `ABC123XYZ`
3. En el admin del barco, pegá ese ID en el campo "YouTube video ID".
4. Tildá "Publicar en YouTube" cuando guardes — la integración actualiza el título y descripción del video.

---

## Si algo no funciona

| Problema | Qué hacer |
|---|---|
| El paso 5 no me deja "Publicar app" | Probablemente faltan datos en la pantalla de consentimiento (logo, email, dominio). Volvé al paso 4 y completá todos los campos obligatorios. |
| Después de publicar dice "Token has been expired" cada 7 días | La app sigue en Testing. Verificá en el paso 4 que diga "En producción". Si no, repetí paso 5 y avisale al equipo técnico para regenerar el Refresh Token. |
| Google dice "Access blocked" cuando intento autorizar (paso 7) | Verificá que estés logueado con la cuenta del paso 1, y que la app esté en "Producción" (paso 5). |
| Olvidé el Client Secret | En Google Cloud Console → Credenciales → click en la credencial → "Reset secret". Pasale al equipo técnico el valor nuevo y autorizá de nuevo (paso 7). |
| Tengo varios canales en mi cuenta de Google y la integración modifica el equivocado | El canal que se modifica es el "principal" de la cuenta. En YouTube Studio → Configuración → seleccionar el canal correcto antes de autorizar. |

---

## Fuentes

- [Google — Pantalla de consentimiento de OAuth](https://support.google.com/cloud/answer/15549945?hl=en)
- [Google — Verificación de apps OAuth](https://support.google.com/cloud/answer/13463073?hl=en)
- [YouTube — Buscar el ID de canal y de usuario](https://support.google.com/youtube/answer/3250431?hl=es)
- [Google — Implementing OAuth 2.0 (YouTube Data API)](https://developers.google.com/youtube/v3/guides/authentication)
