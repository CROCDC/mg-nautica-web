# Integraciones de publicación — MG Náutica

Documento de referencia para las integraciones activas y planificadas. Cada sección describe cómo funciona la integración, las credenciales necesarias, y el formato exacto de la publicación.

---

## Índice

- [Arquitectura general](#arquitectura-general)
- [Mercado Libre (MLU / MLA)](#mercado-libre-mlu--mla)
- [Instagram](#instagram)
- [Facebook](#facebook)

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

### Formato de publicación

```json
{
  "title": "Velero Bavaria 37 2010 impecable",
  "category_id": "MLU109891",
  "price": 85000.0,
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
    { "id": "BOAT_YEAR",   "value_name": "2010" },
    { "id": "BRAND",       "value_name": "Bavaria" },
    { "id": "MODEL",       "value_name": "37" },
    { "id": "TOTAL_LENGTH","value_name": "11.3", "value_struct": { "number": 11.3, "unit": "m" } },
    { "id": "BEAM",        "value_name": "3.75", "value_struct": { "number": 3.75, "unit": "m" } },
    { "id": "DRAFT",       "value_name": "1.9",  "value_struct": { "number": 1.9,  "unit": "m" } },
    { "id": "DISPLACEMENT","value_name": "7.2",  "value_struct": { "number": 7.2,  "unit": "t" } },
    { "id": "VEHICLE_CONDITION", "value_name": "Usado" }
  ]
}
```

La descripción se envía en un request separado: `POST /items/{item_id}/description` con `{ "plain_text": "..." }`.

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

---

## Instagram

**Estado**: Activo  
**Archivo principal**: `app/integrations/instagram/service.py`  
**API**: Facebook Graph API v19.0

### Credenciales (env vars)

| Variable | Descripción |
|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Token de acceso de larga duración (Instagram Business) |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | ID de la cuenta de Instagram Business |

### Flujo de publicación

1. Se selecciona la foto marcada como `is_primary` (o la primera si no hay ninguna).
2. Se genera la caption automáticamente.
3. Se crea un *media container*: `POST /{account_id}/media`.
4. Se publica el container: `POST /{account_id}/media_publish`.

Solo soporta imágenes individuales (no carruseles aún).

### Formato de la caption

```
🚢 {título del barco}
{año} · {eslora}m eslora
💰 US$ {precio}
📍 {ciudad}, {país}

{primeros 400 caracteres de la descripción}…

#nautica #barcos #veleros #yachts #mgNautica #embarcaciones #venta
```

**Ejemplo real:**
```
🚢 Velero Bavaria 37 2010
2010 · 11.3m eslora
💰 US$ 85,000
📍 Montevideo, Uruguay

Excelente estado general. Motor Volvo Penta 50hp con 850 hs. Completo de electrónica: plotter, AIS, piloto automático, VHF. Velas nuevas 2022…

#nautica #barcos #veleros #yachts #mgNautica #embarcaciones #venta
```

### Comportamiento con múltiples fotos

- Si el barco tiene **1 foto**: publica como imagen individual.
- Si tiene **2 o más fotos**: publica como **carrusel** (máximo 10 imágenes, límite de la API).
- La caption siempre va en el post principal (no en cada item del carrusel).

### Limitaciones actuales

- No guarda el media ID publicado en el modelo `boat` (no hay campo `instagram_post_id` aún).
- El token de acceso debe renovarse manualmente cada 60 días.

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

> El token de página de larga duración no expira si la app está verificada. Se puede obtener a través del mismo token de usuario de Instagram si se usa una app de Meta que tenga ambos permisos.

### Flujo de publicación planeado

Facebook permite publicar posts con imagen(es) en una página. El flujo recomendado para carrusel/múltiples fotos:

1. **Opción A — Post con imagen única** (similar a Instagram):
   - `POST /{page_id}/photos?url={url}&caption={caption}&published=true`

2. **Opción B — Post con múltiples imágenes (carrusel)** (preferido para barcos):
   - Subir cada foto como no-publicada: `POST /{page_id}/photos?url={url}&published=false` → obtener `photo_id` de cada una.
   - Crear el post combinando los IDs: `POST /{page_id}/feed` con `attached_media`.

### Formato de publicación propuesto

**Caption** (más larga que Instagram, sin límite de 2200 chars como IG, Facebook no tiene límite práctico relevante):

```
🚢 {título del barco}

📅 Año: {año}
📏 Eslora: {eslora}m | Manga: {manga}m | Calado: {calado}m
🏗️ Astillero: {astillero} | Modelo: {model_name}
⚓ Tipo: {tipo de barco}
📍 Ubicación: {ciudad}, {país}
💰 Precio: US$ {precio}

{descripción completa — sin límite de 400 chars}

📞 Consultas: {teléfono/web de MG Náutica}

#nautica #barcos #veleros #yachts #mgNautica #embarcaciones #venta #uruguay #argentina
```

**Diferencias clave respecto a Instagram:**
- Descripción completa (no truncada a 400 caracteres).
- Incluye más datos técnicos (manga, calado, astillero).
- Puede incluir datos de contacto explícitos.
- Soporta múltiples fotos en el mismo post.
- No usa emojis de forma obligatoria (pero ayudan al engagement).

### Campos a agregar en `boat` para persistir estado

```python
# Propuesta de campos nuevos (migración necesaria)
facebook_post_id   = db.Column(db.String(64))
facebook_post_url  = db.Column(db.String(500))
facebook_synced_at = db.Column(db.DateTime)
```

### Permisos de app Meta requeridos

- `pages_manage_posts`
- `pages_read_engagement`
- `pages_show_list`
- Para fotos: `pages_manage_posts` es suficiente

### Notas de implementación

- Reutilizar el `FACEBOOK_PAGE_ACCESS_TOKEN` también para Instagram si la app Meta es la misma (el token de usuario de Meta puede generar tokens para ambos).
- El `InstagramService` actual usa `INSTAGRAM_ACCESS_TOKEN` separado; al migrar a app unificada, ambas podrían compartir credenciales.
- Considerar agregar `facebook_post_id` al modelo antes de implementar el servicio para tener todo listo cuando se active.
