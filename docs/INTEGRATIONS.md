# Integraciones de publicación — MG Náutica

Documento de referencia para las integraciones activas y planificadas. Cada sección describe cómo funciona la integración técnica, las credenciales necesarias, y el formato exacto de cada publicación con ejemplos reales.

> Para guías paso a paso de **cómo obtener cada credencial** ver [docs/integrations/](docs/integrations/README.md).

---

## Índice

- [Arquitectura general](#arquitectura-general)
- [Cuerpo compartido entre plataformas](#cuerpo-compartido-entre-plataformas)
- [Instagram](#instagram)
- [Facebook](#facebook)
- [YouTube](#youtube)
- [WhatsApp](#whatsapp)
- [Mercado Libre (MLU / MLA)](#mercado-libre-mlu--mla)

---

## Arquitectura general

El flujo de publicación es el mismo para todas las plataformas:

```
Admin crea/edita barco
    → Checkbox "Publicar en X"
    → app/services/publish.py  (orquestador)
        → app/integrations/<plataforma>/service.py  (lógica de plataforma)
```

El estado de cada publicación se persiste en la tabla `boat` (campos `<plataforma>_*`) o en una tabla de credenciales separada.

---

## Cuerpo compartido entre plataformas

Instagram, Facebook y YouTube usan **el mismo cuerpo de texto**. Solo varía el título según la plataforma (ver cada sección). El cuerpo no lleva hashtags ni emojis.

### Template del cuerpo

```
{TIPO_MAYUS} EN VENTA – {MODELO}

{párrafo introductorio: descripción libre del barco}

DATOS GENERALES
Astillero: {astillero}
Modelo: {modelo}
Año: {año}
Eslora: {eslora} mts
Manga: {manga} mts
Calado: {calado} mts
Material: {material_casco}
Cubierta: {material_cubierta}        ← omitir si no aplica

MOTOR Y CAPACIDADES
Motor: {motor_marca} {motor_hp} HP
Combustible: {tipo_combustible}

Tanque de combustible: {combustible_litros} L
Tanque de agua: {agua_litros} L

INTERIOR Y CONFORT
{lista de ítems, uno por línea}

NAVEGACIÓN Y VELAMEN              ← solo para veleros
{lista de ítems, uno por línea}

ESTADO GENERAL
{descripción del estado actual}

DETALLE IMPORTANTE                ← omitir si no hay disclaimers
{texto de advertencia/aclaración}

CONDICIONES
Comisión MG Náutica: {comision_pct}% sobre el valor de venta

CONSULTAS
Contactanos para más información, fotos y coordinar visita
```

### Ejemplo real — Jeanneau Sun Odyssey 54 DS

> Barco de referencia. URL: https://mgnautica.nexttech.com.ar/boats/velero-jeanneau-sun-odyssey-54-ds-oportunidad

```
VELERO EN VENTA – SUN ODYSSEY 54 DS

Velero de crucero oceánico de gran porte, reconocido por su confort, autonomía y excelente navegación. Ideal para vida a bordo o travesías largas.

DATOS GENERALES
Astillero: Jeanneau
Modelo: Sun Odyssey 54 DS (Deck Saloon)
Año: 2006
Eslora: 16,70 mts
Manga: 4,85 mts
Calado: 2,00 mts
Material: Fibra de vidrio
Cubierta: Teca

MOTOR Y CAPACIDADES
Motor: Yanmar 100 HP
Combustible: Diésel

Tanque de combustible: 400 L
Tanque de agua: 900 L

INTERIOR Y CONFORT
Amplio salón tipo deck saloon con excelente luminosidad
Dinet de grandes dimensiones
Camarote principal en popa con cama matrimonial, baño en suite y ducha
2 camarotes en proa
Múltiples baños
Cocina completa
Gran habitabilidad para vida a bordo

NAVEGACIÓN Y VELAMEN
Aparejo sloop
Mayor enrollable
Enrollador de proa
Maniobras centralizadas en cockpit
Velero oceánico categoría A (apto alta mar)

ESTADO GENERAL
Actualmente en lista de espera en varadero en Piriápolis
A la espera de trabajos de pintura
Generador instalado (actualmente fuera de servicio)

DETALLE IMPORTANTE
La embarcación se vende en el estado en que se encuentra, con el equipamiento existente a bordo.
No se cuenta con inventario detallado completo al momento.

CONDICIONES
Comisión MG Náutica: 4% sobre el valor de venta

CONSULTAS
Contactanos para más información, fotos y coordinar visita
```

---

## Instagram

**Estado**: Activo — integración automática pendiente de alinearse con el formato real  
**Archivo principal**: `app/integrations/instagram/service.py`  
**API**: Facebook Graph API v19.0

### Credenciales (env vars)

| Variable | Descripción |
|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Token de acceso de larga duración (Instagram Business) |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | ID de la cuenta de Instagram Business |

> El token expira cada 60 días y debe renovarse manualmente.

### Flujo de publicación

1. Si hay 1 foto: crea un media container con imagen individual → publica.
2. Si hay 2–10 fotos: crea un child container por foto (`is_carousel_item=true`) → crea container `CAROUSEL` con todos los IDs → publica.
3. La caption siempre va en el container principal, no en los items del carrusel.

### Formato del título (primera línea)

```
U$S {precio} | {TIPO_MAYUS} EN VENTA – {MODELO}
```

**Ejemplo real:**
```
U$S 130.000 | VELERO EN VENTA – SUN ODYSSEY 54 DS
```

Reglas:
- Precio con punto como separador de miles (estilo uruguayo): `130.000`, no `130,000`
- Tipo en mayúsculas: VELERO, LANCHA, CATAMARÁN, YATE, etc.
- Modelo tal como aparece en la ficha del barco

### Publicación completa de referencia

```
U$S 130.000 | VELERO EN VENTA – SUN ODYSSEY 54 DS

Velero de crucero oceánico de gran porte, reconocido por su confort, autonomía y excelente navegación. Ideal para vida a bordo o travesías largas.

DATOS GENERALES
Astillero: Jeanneau
Modelo: Sun Odyssey 54 DS (Deck Saloon)
Año: 2006
Eslora: 16,70 mts
Manga: 4,85 mts
Calado: 2,00
Material: Fibra de vidrio
Cubierta: Teca

MOTOR Y CAPACIDADES
Motor: Yanmar 100 HP
Combustible: Diésel

Tanque de combustible: 400 L
Tanque de agua: 900 L

INTERIOR Y CONFORT
Amplio salón tipo deck saloon con excelente luminosidad
Dinet de grandes dimensiones
Camarote principal en popa con cama matrimonial, baño en suite y ducha
2 camarotes en proa
Múltiples baños
Cocina completa
Gran habitabilidad para vida a bordo

NAVEGACIÓN Y VELAMEN
Aparejo sloop
Mayor enrollable
Enrollador de proa
Maniobras centralizadas en cockpit
Velero oceánico categoría A (apto alta mar)

ESTADO GENERAL
Actualmente en lista de espera en varadero en Piriápolis
A la espera de trabajos de pintura
Generador instalado (actualmente fuera de servicio)

DETALLE IMPORTANTE
La embarcación se vende en el estado en que se encuentra, con el equipamiento existente a bordo.
No se cuenta con inventario detallado completo al momento.

CONDICIONES
Comisión MG Náutica: 4% sobre el valor de venta

CONSULTAS
Contactanos para más información, fotos y coordinar visita
```

### Notas

- El generador automático actual (`_build_caption`) produce un formato distinto (corto, con emojis). Debe reemplazarse por el template real antes de activar la integración automática.
- Límite de Instagram: 2.200 caracteres por caption. El cuerpo completo puede acercarse a ese límite en barcos con muchas specs — monitorear.
- No se persiste el media ID publicado en el modelo `boat` (no hay campo `instagram_post_id` aún).

---

## Facebook

**Estado**: Planificado — en desarrollo  
**API**: Facebook Graph API v21.0 (o superior)  
**Archivo futuro**: `app/integrations/facebook/service.py`

### Credenciales necesarias (env vars)

| Variable | Descripción |
|---|---|
| `FACEBOOK_PAGE_ACCESS_TOKEN` | Token de página con permisos `pages_manage_posts`, `pages_read_engagement` |
| `FACEBOOK_PAGE_ID` | ID de la página de Facebook de MG Náutica |

> El token de página de larga duración no expira si la app está verificada. Puede generarse desde el mismo token de usuario Meta si la app tiene permisos para Instagram y Facebook simultáneamente.

### Flujo de publicación planeado

Para posts con múltiples fotos (preferido para barcos):

1. Subir cada foto como no-publicada: `POST /{page_id}/photos?url={url}&published=false` → obtener `photo_id`.
2. Crear el post con todas las fotos: `POST /{page_id}/feed` con `attached_media=[{"media_fbid": id1}, ...]` y el texto.

Para foto única: `POST /{page_id}/photos?url={url}&caption={texto}&published=true`.

### Formato del título (primera línea)

Idéntico a Instagram:

```
U$S {precio} | {TIPO_MAYUS} EN VENTA – {MODELO}
```

**Ejemplo real:**
```
U$S 130.000 | VELERO EN VENTA – SUN ODYSSEY 54 DS
```

### Publicación completa de referencia

El cuerpo es idéntico al de Instagram (ver sección anterior). Facebook no tiene límite práctico de caracteres, por lo que el texto completo se publica sin truncar.

```
U$S 130.000 | VELERO EN VENTA – SUN ODYSSEY 54 DS
Velero de crucero oceánico de gran porte, reconocido por su confort, autonomía y excelente navegación. Ideal para vida a bordo o travesías largas.
DATOS GENERALES
Astillero: Jeanneau
Modelo: Sun Odyssey 54 DS (Deck Saloon)
Año: 2006
Eslora: 16,70 mts
Manga: 4,85 mts
Calado: 2,00 
Material: Fibra de vidrio
Cubierta: Teca
MOTOR Y CAPACIDADES
Motor: Yanmar 100 HP
Combustible: Diésel
Tanque de combustible: 400 L
Tanque de agua: 900 L
INTERIOR Y CONFORT
Amplio salón tipo deck saloon con excelente luminosidad
Dinet de grandes dimensiones
Camarote principal en popa con cama matrimonial, baño en suite y ducha
2 camarotes en proa
Múltiples baños 
Cocina completa
Gran habitabilidad para vida a bordo
NAVEGACIÓN Y VELAMEN
Aparejo sloop
Mayor enrollable
Enrollador de proa
Maniobras centralizadas en cockpit
Velero oceánico categoría A (apto alta mar)
ESTADO GENERAL
Actualmente en  lista de espera en varadero en Piriápolis
A la espera de trabajos de pintura
Generador instalado (actualmente fuera de servicio)
DETALLE IMPORTANTE
La embarcación se vende en el estado en que se encuentra, con el equipamiento existente a bordo.
No se cuenta con inventario detallado completo al momento.
CONDICIONES
Comisión MG Náutica: 4% sobre el valor de venta
CONSULTAS
Contactanos para más información, fotos y coordinar visita
```

> Nota: en el ejemplo real de Facebook el espaciado entre secciones es más compacto (sin línea en blanco entre título de sección y su contenido). El contenido es idéntico al de Instagram.

### Campos a agregar en `boat` para persistir estado

```python
facebook_post_id   = db.Column(db.String(64))
facebook_post_url  = db.Column(db.String(500))
facebook_synced_at = db.Column(db.DateTime)
```

### Permisos de app Meta requeridos

- `pages_manage_posts`
- `pages_read_engagement`
- `pages_show_list`

---

## YouTube

**Estado**: Activo — solo metadata (título y descripción)  
**Archivo principal**: `app/integrations/youtube/service.py`  
**API**: YouTube Data API v3

### Flujo

1. El video se sube **manualmente** a YouTube.
2. En el admin se guarda el `youtube_video_id` del video (ej: `S2s9CV2zrpQ`).
3. Al tildar "Publicar en YouTube" al guardar el barco, la integración hace `PUT /videos` con el título (`build_title`) y descripción (`build_body`) del barco. Preserva categoryId, tags y demás metadata existente.

> No sube videos. Para automatizar la subida (Shorts armados con las fotos del barco) hay que extender el servicio.

### Credenciales necesarias (env vars)

| Variable | Descripción |
|---|---|
| `YOUTUBE_CLIENT_ID` | Client ID de la app OAuth Google |
| `YOUTUBE_CLIENT_SECRET` | Client Secret de la app OAuth Google |
| `YOUTUBE_REFRESH_TOKEN` | Refresh token de larga duración (no expira si la app es de testing/published) |

El access token se intercambia bajo demanda desde el refresh token (`POST https://oauth2.googleapis.com/token`).

### Estado persistido en `boat`

| Campo | Descripción |
|---|---|
| `youtube_video_id` | ID del video en YouTube (input manual desde el admin) |
| `youtube_synced_at` | Timestamp del último sync |

### Formato del título

```
U$S {precio} | {ASTILLERO} {MODELO} | EN VENTA {bandera_emoji} OPORTUNIDAD
```

**Ejemplo real:**
```
U$S 130.000 | JEANNEAU SUN ODYSSEY 54 DS | EN VENTA 🇺🇾 OPORTUNIDAD
```

Diferencias respecto a Instagram/Facebook:
- Incluye el **astillero** explícitamente (mejor para SEO en YouTube).
- Agrega `OPORTUNIDAD` cuando hay rebaja de precio.
- Lleva el emoji de bandera del país donde está el barco (🇺🇾 Uruguay, 🇦🇷 Argentina).
- El modelo va sin guión: `JEANNEAU SUN ODYSSEY 54 DS`, no `VELERO EN VENTA – ...`.

### Bandera por país

| País | Emoji |
|---|---|
| Uruguay | 🇺🇾 |
| Argentina | 🇦🇷 |
| Otros | omitir |

### Publicación completa de referencia

**Título:**
```
U$S 130.000 | JEANNEAU SUN ODYSSEY 54 DS | EN VENTA 🇺🇾 OPORTUNIDAD
```

**Descripción** (mismo cuerpo compartido):
```
VELERO EN VENTA – SUN ODYSSEY 54 DS

Velero de crucero oceánico de gran porte, reconocido por su confort, autonomía y excelente navegación. Ideal para vida a bordo o travesías largas.

DATOS GENERALES
Astillero: Jeanneau
Modelo: Sun Odyssey 54 DS (Deck Saloon)
Año: 2006
Eslora: 16,70 mts
Manga: 4,85 mts
Calado: 2,00 mts
Material: Fibra de vidrio
Cubierta: Teca

MOTOR Y CAPACIDADES
Motor: Yanmar 100 HP
Combustible: Diésel

Tanque de combustible: 400 L
Tanque de agua: 900 L

INTERIOR Y CONFORT
Amplio salón tipo deck saloon con excelente luminosidad
Dinet de grandes dimensiones
Camarote principal en popa con cama matrimonial, baño en suite y ducha
2 camarotes en proa
Múltiples baños
Cocina completa
Gran habitabilidad para vida a bordo

NAVEGACIÓN Y VELAMEN
Aparejo sloop
Mayor enrollable
Enrollador de proa
Maniobras centralizadas en cockpit
Velero oceánico categoría A (apto alta mar)

ESTADO GENERAL
Actualmente en lista de espera en varadero en Piriápolis
A la espera de trabajos de pintura
Generador instalado (actualmente fuera de servicio)

DETALLE IMPORTANTE
La embarcación se vende en el estado en que se encuentra, con el equipamiento existente a bordo.
No se cuenta con inventario detallado completo al momento.

CONDICIONES
Comisión MG Náutica: 4% sobre el valor de venta

CONSULTAS
Contactanos para más información, fotos y coordinar visita
```

---

## WhatsApp

**Estado**: Activo — sincronización con WhatsApp Business Catalog  
**Archivo principal**: `app/integrations/whatsapp/service.py`  
**Serializer**: `app/integrations/whatsapp/serializer.py`  
**API**: Meta Commerce Catalog API (mismo backend que Facebook Shops)

A diferencia de las redes sociales, WhatsApp Catalog **no publica un post**, sino que sincroniza el barco como **producto en el catálogo** con campos estructurados (similar a Mercado Libre). Una vez sincronizado, el producto aparece disponible en el chat de WhatsApp Business.

### Credenciales necesarias (env vars)

| Variable | Descripción |
|---|---|
| `WHATSAPP_CATALOG_ID` | ID del catálogo en Meta Business Manager |
| `WHATSAPP_ACCESS_TOKEN` | Token con permiso `catalog_management` (puede ser el mismo `FACEBOOK_PAGE_ACCESS_TOKEN` si la app comparte permisos) |
| `PUBLIC_SITE_URL` | URL pública del sitio (default: `https://mgnautica.com`); se usa para el campo `url` del producto |

### Flujo

Endpoint: `POST /{catalog_id}/items_batch` con `method: "UPDATE"` (upsert por `retailer_id`).

El `retailer_id` se construye como `boat-{slug}` — es estable, así que la misma operación crea el producto la primera vez y lo actualiza en llamadas siguientes.

### Formato del producto

```json
{
  "retailer_id": "boat-velero-jeanneau-sun-odyssey-54-ds-oportunidad",
  "name": "U$S 130.000 | VELERO EN VENTA – SUN ODYSSEY 54 DS",
  "description": "{cuerpo compartido completo}",
  "price": 13000000,
  "currency": "USD",
  "image_url": "https://cdn.mgnautica.com/.../foto-1.jpg",
  "additional_image_urls": ["...", "..."],
  "availability": "in stock",
  "condition": "used",
  "url": "https://mgnautica.com/boats/velero-jeanneau-sun-odyssey-54-ds-oportunidad",
  "brand": "Jeanneau"
}
```

Notas:
- `price` se envía en **centavos** (Meta lo requiere así).
- `name` reutiliza `build_title` (truncado a 150 chars).
- `description` reutiliza `build_body` (truncado a 9999 chars).
- `additional_image_urls` lleva hasta 9 fotos extra (límite de Meta: 10 imágenes totales).

### Operaciones

- **Sync (upsert)**: `WhatsAppService.sync_boat(boat)` — crea o actualiza por `retailer_id`.
- **Delete**: `WhatsAppService.delete_boat(boat)` — quita el producto del catálogo (útil cuando se vende o se cierra).

### Estado persistido en `boat`

| Campo | Descripción |
|---|---|
| `whatsapp_synced_at` | Timestamp del último sync |

> No se persiste el `retailer_id` porque es derivable del slug (`boat-{slug}`).

### Permiso de app Meta requerido

- `catalog_management`

---

## Mercado Libre (MLU / MLA)

**Estado**: Activo  
**Archivo principal**: `app/integrations/mercadolibre/service.py`  
**Serializer**: `app/integrations/mercadolibre/serializer.py`  
**Auth**: `app/integrations/mercadolibre/auth.py`  
**Cliente HTTP**: `app/integrations/mercadolibre/client.py`

### Credenciales (env vars)

| Variable | Descripción |
|---|---|
| `MELI_APP_ID` | Client ID de la app MELI |
| `MELI_SECRET` | Client Secret de la app MELI |
| `MELI_REDIRECT_URI` | URI de callback OAuth |

Los tokens de acceso y refresh se guardan en la tabla `meli_credentials` (una fila por sitio: `MLU`, `MLA`). Se renuevan automáticamente 5 minutos antes de expirar (vida útil: 6 horas).

### Sitios soportados

| Site ID | País | Moneda |
|---|---|---|
| `MLU` | Uruguay | USD |
| `MLA` | Argentina | USD |

### Formato del título MELI

El título en MELI sigue sus propias restricciones (máx. 60 caracteres, sin caracteres especiales como `|` o `–`):

```
{Tipo} {Astillero} {Modelo} {Año}
```

**Ejemplo:**
```
Velero Jeanneau Sun Odyssey 54 DS 2006
```

### Formato del payload principal

```json
{
  "title": "Velero Jeanneau Sun Odyssey 54 DS 2006",
  "category_id": "MLU109891",
  "price": 130000.0,
  "currency_id": "USD",
  "available_quantity": 1,
  "buying_mode": "buy_it_now",
  "listing_type_id": "gold_special",
  "condition": "used",
  "pictures": [
    { "source": "https://cdn.mgnautica.com/fotos/barco-1.jpg" },
    { "source": "https://cdn.mgnautica.com/fotos/barco-2.jpg" }
  ],
  "attributes": [
    { "id": "BOAT_YEAR",    "value_name": "2006" },
    { "id": "BRAND",        "value_name": "Jeanneau" },
    { "id": "MODEL",        "value_name": "Sun Odyssey 54 DS" },
    { "id": "TOTAL_LENGTH", "value_name": "16.7", "value_struct": { "number": 16.7, "unit": "m" } },
    { "id": "BEAM",         "value_name": "4.85", "value_struct": { "number": 4.85, "unit": "m" } },
    { "id": "DRAFT",        "value_name": "2.0",  "value_struct": { "number": 2.0,  "unit": "m" } },
    { "id": "VEHICLE_CONDITION", "value_name": "Usado" }
  ]
}
```

La descripción se envía por separado: `POST /items/{item_id}/description` con `{ "plain_text": "..." }`. Usar el mismo cuerpo compartido descripto arriba.

### Categorías por tipo de barco

| Tipo | MLU | MLA |
|---|---|---|
| Velero | MLU109891 | MLA430379 |
| Lancha | MLU109890 | MLA430389 |
| Crucero | MLU109891 | MLA430379 |
| Catamarán | MLU109891 | MLA430379 |
| Yate | MLU109891 | MLA430379 |
| Ballenera | MLU109890 | MLA430389 |
| Otro | MLU109890 | MLA430389 |

### Estado persistido en `boat`

| Campo | Descripción |
|---|---|
| `meli_mlu_item_id` / `meli_mla_item_id` | ID del ítem en MELI |
| `meli_mlu_status` / `meli_mla_status` | Estado: `active`, `paused`, `closed` |
| `meli_mlu_permalink` / `meli_mla_permalink` | URL pública del aviso |
| `meli_mlu_synced_at` / `meli_mla_synced_at` | Timestamp de última sincronización |

### Operaciones disponibles

- **Publish**: primera publicación (crea ítem nuevo)
- **Update**: sincroniza título, precio y fotos
- **Pause**: pausa el aviso
- **Activate**: reactiva un aviso pausado
- **Close**: cierra el aviso permanentemente
