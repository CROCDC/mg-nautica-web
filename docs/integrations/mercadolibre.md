# Mercado Libre — cómo obtener las credenciales

Esta guía te explica cómo crear una "aplicación" en Mercado Libre para que MG Náutica pueda publicar avisos de barcos automáticamente. Vas a hacer todo desde la web, son ~10 minutos.

> Si querés publicar en Uruguay **y** Argentina, vas a tener que repetir esta guía para cada país (con la cuenta de vendedor de cada país).
>
> **Solo desde computadora.**

## Lo que vamos a obtener

Al final de esta guía vas a tener tres datos que entregar al equipo técnico:

1. **App ID** (un número largo, ej: `1234567890123456`)
2. **Secret Key** (una clave secreta tipo contraseña)
3. **Redirect URI** (una URL que vamos a definir junto con el equipo técnico)

> **Importante**: una vez que entregues estos datos, **el equipo técnico se encarga del resto**. Ellos hacen la conexión final con tu cuenta de vendedor desde el servidor — vos no tenés que hacer nada más.

---

## Paso 1 — Pedile al equipo técnico la "Redirect URI"

Antes de crear la app, necesitás que el equipo técnico te pase una URL específica que vas a tener que pegar en Mercado Libre. Es algo del estilo:

```
https://mgnautica.com/admin/meli/oauth/callback
```

Mandales un mensaje pidiéndoles "la Redirect URI para Mercado Libre". Es un dato que ellos definen una vez y no cambia.

> Mientras esperás, podés avanzar con los pasos 2 y 3.

## Paso 2 — Iniciar sesión con la cuenta de vendedor

1. Asegurate de tener la cuenta de vendedor de MG Náutica en Mercado Libre (la cuenta desde donde se publican los barcos hoy).
2. Si vas a empezar por **Uruguay**, abrí: https://developers.mercadolibre.com.uy/devcenter
3. Si vas a empezar por **Argentina**, abrí: https://developers.mercadolibre.com.ar/devcenter
4. Click en **"Mis aplicaciones"** o **"DevCenter"** arriba a la derecha.
5. Iniciá sesión con la cuenta de vendedor de MG Náutica.

> **Importante**: tiene que ser la misma cuenta con la que se publican los barcos. Si entrás con una cuenta personal, la integración no va a poder publicar después.

## Paso 3 — Crear la aplicación

1. Click en el botón verde **"Crear nueva aplicación"** (arriba a la derecha de la pantalla).
2. Vas a ver un formulario. Completá así:

| Campo | Qué poner |
|---|---|
| **Nombre** | `MG Nautica` (o `MG Nautica MLU` si vas a hacer una para cada país) |
| **Nombre corto** | `mgnautica` |
| **Descripción** | "Sincronización de catálogo de embarcaciones de MG Náutica" |
| **URL del sitio web** | `https://mgnautica.com` |
| **Logo** | Subí el logo de MG Náutica (cualquier imagen cuadrada sirve) |
| **Redirect URI** | La URL que te pasó el equipo técnico en el paso 1 |
| **Scopes / Permisos** | **Marcá las tres**: `read`, `write`, `offline_access` |
| **Topics / Notificaciones** | Dejalo vacío o desmarcado |

> El campo **`offline_access`** es el más importante. Si te olvidás de marcarlo, la conexión se rompe cada 6 horas y hay que rehacer todo. **Verificá dos veces que esté tildado.**

3. Click en **"Guardar"** al final del formulario.

## Paso 4 — Copiar las credenciales

Después de guardar, Mercado Libre te lleva a la pantalla de tu aplicación. Ahí vas a ver:

- **App ID**: un número largo. Copialo.
- **Secret Key**: una clave secreta. Click en "Mostrar" (o ícono del ojo) para revelarla. Copiala.

> ⚠️ **La Secret Key es como una contraseña.** No la mandes por email/WhatsApp en texto plano. Pasala al equipo técnico por un canal seguro (1Password, gestor de credenciales, mensaje cifrado).

## Paso 5 — Si querés conectar el otro país

Repetí los pasos 2 a 4 entrando al portal del otro país (`developers.mercadolibre.com.ar` si empezaste por Uruguay, o viceversa). Cada país necesita su propia aplicación porque las cuentas de vendedor son distintas.

Vas a obtener un **App ID** y **Secret Key** distintos para el segundo país. Pasaselos al equipo técnico también.

## Paso 6 — Autorizar el acceso (cuando te lo pida el equipo técnico)

Una vez que el equipo técnico cargó tus credenciales en el sistema, te van a mandar un **link de autorización** (algo como `https://auth.mercadolibre.com.uy/authorization?...`).

1. Hacé click en el link **logueado con la cuenta de vendedor del paso 2**.
2. Mercado Libre te muestra una pantalla preguntando si autorizás a "MG Nautica" a manejar tu cuenta.
3. Click en **"Autorizar"**.
4. Listo — la conexión queda activa. El equipo técnico recibe los tokens automáticamente desde el servidor.

> No copies ni pegues nada en este paso, no hay que enviarles nada más. Después de hacer click en "Autorizar", el sistema se encarga del resto.

---

## Lo que tenés que entregar al equipo técnico

Por cada país (Uruguay y/o Argentina) le pasás:

```
País: Uruguay (o Argentina)
MELI_APP_ID = (el número que copiaste en el paso 4)
MELI_SECRET = (la Secret Key del paso 4)
```

> El **Redirect URI** ya lo conocen ellos (te lo pasaron en el paso 1) — no hace falta que se los pases de vuelta.

---

## Mantenimiento futuro

- La conexión queda activa **mientras se publique al menos un barco cada 6 meses**. Si la cuenta queda inactiva más de 6 meses, hay que volver a hacer el paso 6 (autorizar de nuevo). El equipo técnico te avisa si pasa.
- **No borres la aplicación** desde el panel de developers de Mercado Libre. Si la borrás, hay que rehacer todo desde el paso 1.
- Si cambia tu contraseña de Mercado Libre, la conexión NO se rompe. Solo se rompe si revocás manualmente el acceso desde tu cuenta.

---

## Si algo no funciona

| Problema | Qué hacer |
|---|---|
| No puedo entrar a developers.mercadolibre.com.uy | Probá con la cuenta personal del dueño de la cuenta de vendedor; a veces piden datos extra de identidad la primera vez |
| El sistema dice que el Redirect URI está mal | Verificá con el equipo técnico que la URL que pusiste en el paso 3 sea exactamente la misma que tienen configurada en el servidor |
| Después de autorizar dice "App not authorized" | Volvé al paso 3, abrí la app, y verificá que `offline_access` esté tildado. Si no estaba, marcalo y guardá; después repetí el paso 6. |
| El equipo técnico dice que se rompió la conexión | Pediles que te pasen el link de autorización (paso 6) de nuevo |

---

## Fuentes

- [Mercado Libre — Crear una aplicación](https://developers.mercadolibre.com.ar/es_ar/crea-una-aplicacion-en-mercado-libre-es)
- [Mercado Libre — Primeros pasos](https://developers.mercadolibre.com.ar/es_ar/primeros-pasos)
- [Mercado Libre — Autenticación y autorización](https://developers.mercadolibre.com.ar/es_ar/autenticacion-y-autorizacion)
