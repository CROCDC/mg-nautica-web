# Guía Técnica: Integración con la API Pública de Mercado Libre — Uruguay (MLU) y Argentina (MLA) — Marketplace de Embarcaciones

**Versión:** Abril 2026  
**Proyecto:** mg-nautica-web (Flask)  
**Mercados objetivo:** MLU (Uruguay) y MLA (Argentina)

---

## Tabla de Contenidos

1. [Registro de la Aplicación y Credenciales](#1-registro-de-la-aplicación-y-credenciales)
2. [Autenticación y Autorización OAuth 2.0](#2-autenticación-y-autorización-oauth-20)
3. [Publicación de Ítems (Listings)](#3-publicación-de-ítems-listings)
4. [Imágenes y Fotos](#4-imágenes-y-fotos)
5. [Descripción del Ítem](#5-descripción-del-ítem)
6. [Tipos de Publicación (listing_type_id)](#6-tipos-de-publicación-listing_type_id)
7. [Categorías para Embarcaciones — MLU y MLA](#7-categorías-para-embarcaciones--mlu-y-mla)
8. [Atributos Requeridos por Categoría](#8-atributos-requeridos-por-categoría)
9. [Gestión de Publicaciones](#9-gestión-de-publicaciones)
10. [Preguntas y Respuestas](#10-preguntas-y-respuestas)
11. [Webhooks y Notificaciones](#11-webhooks-y-notificaciones)
12. [Rate Limits y Manejo de Errores](#12-rate-limits-y-manejo-de-errores)
13. [Sandbox y Testing](#13-sandbox-y-testing)
14. [Ejemplo Completo: Publicar un Velero en MLU con Precio en USD](#14-ejemplo-completo-publicar-un-velero-en-mlu-con-precio-en-usd)
15. [Mapeo del Modelo de mg-nautica-web a la API de MELI](#15-mapeo-del-modelo-de-mg-nautica-web-a-la-api-de-meli)
16. [Referencia Rápida de Endpoints](#16-referencia-rápida-de-endpoints)

---

## 1. Registro de la Aplicación y Credenciales

### 1.1 Portal de Developers

El portal unificado para registrar aplicaciones es:

```
https://developers.mercadolibre.com.ar/
```

Este portal funciona para todas las jurisdicciones (MLA, MLU, etc.). No existe un portal separado por país.

### 1.2 Pasos para Crear una Aplicación

1. Ir a `https://developers.mercadolibre.com.ar/`
2. Hacer login con una cuenta de Mercado Libre (puede ser una cuenta de prueba).
3. Navegar a **"Mis Aplicaciones"** → **"Crear nueva aplicación"**.
4. Completar:
   - **Nombre de la aplicación**: Máximo 50 caracteres, único en el sitio.
   - **Short Name**: Solo letras, números y guión bajo. Máximo 50 caracteres. Se usa para generar la URL de la app.
   - **Callback URL (Redirect URI)**: URL exacta a donde MELI redirigirá tras autorizar. Debe coincidir exactamente en todas las llamadas OAuth. Ejemplo: `https://mg-nautica.com/auth/callback`
   - Aceptar términos y condiciones.
5. Tras crear la app, la plataforma entrega:
   - **Client ID** (también llamado `APP_ID`): identificador único de la aplicación.
   - **Client Secret**: contraseña de la aplicación. **Nunca exponerlo en código cliente.**

### 1.3 Datos que Devuelve el Portal

```json
{
  "app_id": "123456789",
  "secret_key": "aBcDeFgHiJkL",
  "redirect_uri": "https://mg-nautica.com/auth/callback",
  "scopes": ["read", "write", "offline_access"]
}
```

**Nota importante:** El Client Secret se muestra una sola vez o se puede regenerar desde el panel. Si se regenera, todos los tokens emitidos con el secreto anterior quedan inválidos inmediatamente.

---

## 2. Autenticación y Autorización OAuth 2.0

Mercado Libre implementa el flujo **Authorization Code Grant** de OAuth 2.0 (RFC 6749). Es el único flujo soportado para aplicaciones que operan en nombre de usuarios reales.

### 2.1 URLs Clave

| Recurso | URL |
|---|---|
| API base | `https://api.mercadolibre.com` |
| Autorización MLA (Argentina) | `https://auth.mercadolibre.com.ar/authorization` |
| Autorización MLU (Uruguay) | `https://auth.mercadolibre.com.uy/authorization` |
| Token endpoint (todos los países) | `https://api.mercadolibre.com/oauth/token` |

**Importante:** El endpoint de autorización varía por país, pero el endpoint para intercambiar y refrescar tokens (`/oauth/token`) es **único y global** para todos los sitios.

### 2.2 Scopes Disponibles

| Scope | Descripción |
|---|---|
| `read` | Permite llamadas GET. Acceso de solo lectura. |
| `write` | Permite PUT, POST, DELETE. Necesario para publicar ítems. |
| `offline_access` | Permite obtener un `refresh_token` para mantener la sesión activa sin re-autorización del usuario. **Imprescindible** para integraciones server-side. |

Para una integración completa de marketplace se necesitan los tres scopes: `read write offline_access`.

### 2.3 Flujo Completo: Authorization Code

#### Paso 1 — Redirigir al usuario a la URL de autorización

```python
import urllib.parse

APP_ID = "TU_CLIENT_ID"
REDIRECT_URI = "https://mg-nautica.com/auth/callback"
SITE = "MLU"  # o "MLA"

# Para Uruguay
AUTH_URL_BASE = "https://auth.mercadolibre.com.uy/authorization"
# Para Argentina
# AUTH_URL_BASE = "https://auth.mercadolibre.com.ar/authorization"

params = {
    "response_type": "code",
    "client_id": APP_ID,
    "redirect_uri": REDIRECT_URI,
    "state": "STATE_ALEATORIO_CSRF_PROTECTION",  # valor único por request
}

authorization_url = AUTH_URL_BASE + "?" + urllib.parse.urlencode(params)
# Redirigir al usuario a authorization_url
print(authorization_url)
# https://auth.mercadolibre.com.uy/authorization?response_type=code&client_id=...
```

#### Paso 2 — Recibir el código de autorización

Tras que el usuario autoriza, MELI redirige a:

```
https://mg-nautica.com/auth/callback?code=TG-xxxxxxxxxxxxx&state=STATE_ALEATORIO
```

Verificar que `state` coincide con el enviado (protección CSRF).

#### Paso 3 — Intercambiar el código por tokens

```python
import requests

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
APP_ID = "TU_CLIENT_ID"
APP_SECRET = "TU_CLIENT_SECRET"
REDIRECT_URI = "https://mg-nautica.com/auth/callback"

def exchange_code_for_tokens(auth_code: str) -> dict:
    """
    Intercambia el authorization code por access_token y refresh_token.
    Siempre enviar parámetros en el body, nunca como query string.
    """
    payload = {
        "grant_type": "authorization_code",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    response.raise_for_status()
    return response.json()

tokens = exchange_code_for_tokens("TG-xxxxxxxxxxxxx")
```

**Respuesta esperada:**

```json
{
  "access_token": "APP_USR-1234567890-XXXXXX-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX-XXXXXXX",
  "token_type": "bearer",
  "expires_in": 21600,
  "scope": "read write offline_access",
  "user_id": 123456789,
  "refresh_token": "TG-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX-XXXXXXX"
}
```

| Campo | Descripción |
|---|---|
| `access_token` | Token de acceso a la API. Válido por **6 horas** (21600 segundos). |
| `refresh_token` | Token para renovar el access_token. Válido por **6 meses**. |
| `user_id` | ID del usuario que autorizó. |
| `expires_in` | Segundos hasta expiración del access_token. |

### 2.4 Renovación del Access Token (Refresh)

```python
def refresh_access_token(refresh_token: str) -> dict:
    """
    Renueva el access_token usando el refresh_token.
    El refresh_token también se renueva en cada llamada.
    Guardar el nuevo refresh_token devuelto.
    """
    payload = {
        "grant_type": "refresh_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "refresh_token": refresh_token,
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    response.raise_for_status()
    return response.json()
```

**Respuesta (igual estructura que el token inicial):**

```json
{
  "access_token": "APP_USR-NUEVO-ACCESS-TOKEN...",
  "token_type": "bearer",
  "expires_in": 21600,
  "scope": "read write offline_access",
  "user_id": 123456789,
  "refresh_token": "TG-NUEVO-REFRESH-TOKEN..."
}
```

**CRÍTICO:** Cada llamada de refresh devuelve un **nuevo** refresh_token. El anterior queda invalidado. Siempre persistir el nuevo refresh_token en la base de datos.

### 2.5 Uso del Access Token

```python
def api_get(path: str, access_token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(f"https://api.mercadolibre.com{path}", headers=headers)
    response.raise_for_status()
    return response.json()

# Ejemplo: obtener datos del usuario autenticado
user = api_get("/users/me", access_token)
```

### 2.6 Causas de Invalidación Prematura del Token

Un `access_token` puede invalidarse antes de sus 6 horas si:
- El usuario cambia su contraseña en Mercado Libre.
- La aplicación regenera su Client Secret.
- El usuario revoca los permisos a la aplicación.
- La aplicación no se usa por 4 meses (el refresh_token expira).
- El refresh_token caduca (a los 6 meses de inactividad).

### 2.7 Estrategia de Token Management en Flask

```python
# models/meli_token.py
from datetime import datetime, timedelta
from app import db

class MeliToken(db.Model):
    __tablename__ = "meli_tokens"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, unique=True, nullable=False)
    access_token = db.Column(db.String(512), nullable=False)
    refresh_token = db.Column(db.String(512), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    scope = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def is_expired(self) -> bool:
        # Considerar expirado 5 minutos antes para evitar race conditions
        return datetime.utcnow() >= (self.expires_at - timedelta(minutes=5))
    
    def get_valid_token(self) -> str:
        if self.is_expired():
            new_tokens = refresh_access_token(self.refresh_token)
            self.access_token = new_tokens["access_token"]
            self.refresh_token = new_tokens["refresh_token"]
            self.expires_at = datetime.utcnow() + timedelta(seconds=new_tokens["expires_in"])
            db.session.commit()
        return self.access_token
```

---

## 3. Publicación de Ítems (Listings)

### 3.1 Endpoint de Creación

```
POST https://api.mercadolibre.com/items
Authorization: Bearer {access_token}
Content-Type: application/json
```

### 3.2 Estructura Completa del JSON

```python
item_payload = {
    # === CAMPOS OBLIGATORIOS ===
    "title": "Velero Bavaria 37 2015 - Eslora 11m - Impecable",
    "category_id": "MLU109890",        # Ver sección 7 para IDs correctos
    "price": 85000,                     # Precio numérico
    "currency_id": "USD",               # Ver sección 3.4 para opciones
    "available_quantity": 1,            # Para embarcaciones siempre 1
    "buying_mode": "buy_it_now",        # Para vehículos/embarcaciones
    "listing_type_id": "gold_special",  # Ver sección 6
    "condition": "used",                # "new" o "used"
    
    # === FOTOS (mínimo 1 recomendada) ===
    "pictures": [
        {"source": "https://storage.mg-nautica.com/boats/slug-barco-foto-1.jpg"},
        {"source": "https://storage.mg-nautica.com/boats/slug-barco-foto-2.jpg"},
        # También puede ser el ID de foto presubida: {"id": "MLU-12345"}
    ],
    
    # === ATRIBUTOS DE CATEGORÍA ===
    # Los IDs exactos dependen de la categoría. Ver sección 8.
    "attributes": [
        {"id": "BOAT_YEAR", "value_name": "2015"},
        {"id": "BRAND", "value_name": "Bavaria"},
        {"id": "MODEL", "value_name": "Bavaria 37"},
        {"id": "TOTAL_LENGTH", "value_name": "11", "value_struct": {"number": 11, "unit": "m"}},
        {"id": "ENGINE_TYPE", "value_id": "229873"},   # ID de valor enumerado
        {"id": "FUEL_TYPE", "value_name": "Diesel"},
        {"id": "CABINS_QUANTITY", "value_name": "3"},
        {"id": "VEHICLE_CONDITION", "value_id": "2230581"},  # "Usado"
    ],
    
    # === UBICACIÓN (opcional pero recomendado) ===
    "geolocation": {
        "latitude": -34.9011,
        "longitude": -56.1645
    },
    
    # === VENTAS/GARANTÍA (recomendado para algunos tipos) ===
    # Para embarcaciones usadas no aplica garantía típicamente
    # "sale_terms": [
    #     {"id": "WARRANTY_TYPE", "value_name": "Vendedor"},
    #     {"id": "WARRANTY_TIME", "value_name": "Sin garantía"}
    # ],
}
```

### 3.3 Ejemplo de Llamada Python con requests

```python
import requests
import json

def create_listing(item_data: dict, access_token: str) -> dict:
    """
    Crea una publicación en Mercado Libre.
    Retorna el objeto ítem creado, incluyendo el item_id asignado.
    """
    url = "https://api.mercadolibre.com/items"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    response = requests.post(url, json=item_data, headers=headers)
    
    if response.status_code == 201:
        return response.json()
    else:
        error_body = response.json()
        raise Exception(
            f"Error al crear ítem: HTTP {response.status_code} — "
            f"{error_body.get('message', '')} / {error_body.get('cause', '')}"
        )

item = create_listing(item_payload, access_token)
print(f"Ítem creado: {item['id']}")  # e.g. MLU1234567890
print(f"Permalink: {item['permalink']}")
```

### 3.4 Valores de currency_id por Sitio

| Sitio | Moneda principal | currency_id |
|---|---|---|
| MLU (Uruguay) | Peso uruguayo | `UYU` |
| MLU (Uruguay) | Dólar estadounidense | `USD` (permitido) |
| MLA (Argentina) | Peso argentino | `ARS` |
| MLA (Argentina) | Dólar | `USD` (solo algunos contextos) |

**Para embarcaciones en Uruguay:** Publicar en `USD` es la práctica habitual del mercado y está permitido por la API. Para Argentina, las restricciones cambiarias pueden limitar el uso de `USD`; verificar con `GET /sites/MLA/currencies`.

### 3.5 Valores de condition

| Valor | Descripción |
|---|---|
| `"new"` | Ítem nuevo (sin uso) |
| `"used"` | Ítem usado |

Para embarcaciones de segunda mano siempre usar `"used"`.

### 3.6 Valores de buying_mode

| Valor | Descripción |
|---|---|
| `"buy_it_now"` | Precio fijo. Estándar para embarcaciones. |
| `"auction"` | Subasta. Rara vez usado para embarcaciones. |
| `"classified"` | Clasificado (sin transacción en MELI). Disponible para algunas categorías de vehículos. |

Para embarcaciones en MLU y MLA usar `"buy_it_now"` o `"classified"` según la categoría.

### 3.7 Respuesta de Creación Exitosa (HTTP 201)

```json
{
  "id": "MLU1234567890",
  "site_id": "MLU",
  "title": "Velero Bavaria 37 2015 - Eslora 11m - Impecable",
  "seller_id": 987654321,
  "category_id": "MLU109890",
  "official_store_id": null,
  "price": 85000,
  "currency_id": "USD",
  "available_quantity": 1,
  "sold_quantity": 0,
  "buying_mode": "buy_it_now",
  "listing_type_id": "gold_special",
  "stop_time": "2026-07-26T04:00:00.000Z",
  "condition": "used",
  "permalink": "https://vehiculo.mercadolibre.com.uy/MLU-1234567890-velero-bavaria-37-_JM",
  "thumbnail": "https://http2.mlstatic.com/D_NQ_NP_XXXXX.jpg",
  "pictures": [...],
  "attributes": [...],
  "status": "active",
  "sub_status": [],
  "date_created": "2026-04-26T12:00:00.000Z",
  "last_updated": "2026-04-26T12:00:00.000Z"
}
```

---

## 4. Imágenes y Fotos

### 4.1 Métodos de Adjuntar Fotos

Hay dos formas de asociar fotos a un ítem:

**Método A — URLs directas (más simple):**  
Incluir las URLs públicas directamente en el campo `pictures` del JSON de creación:

```json
"pictures": [
  {"source": "https://storage.mg-nautica.com/boats/barco-1.jpg"},
  {"source": "https://storage.mg-nautica.com/boats/barco-2.jpg"}
]
```

MELI descargará y procesará las imágenes. Las URLs deben ser públicamente accesibles (sin autenticación).

**Método B — Presubida de imágenes (recomendado para mejor control):**

```python
def upload_picture(image_path: str, access_token: str) -> str:
    """
    Sube una imagen a MELI y devuelve el picture_id.
    Usar multipart/form-data.
    """
    url = "https://api.mercadolibre.com/pictures/items/upload"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }
    
    with open(image_path, "rb") as f:
        files = {"file": (image_path, f, "image/jpeg")}
        response = requests.post(url, headers=headers, files=files)
    
    response.raise_for_status()
    return response.json()["id"]  # e.g. "MLU-12345678-XXXX"

# Subir múltiples fotos
picture_ids = []
for photo_path in ["/tmp/barco1.jpg", "/tmp/barco2.jpg"]:
    pid = upload_picture(photo_path, access_token)
    picture_ids.append({"id": pid})

# Luego usar en la creación del ítem
item_payload["pictures"] = picture_ids
```

**Respuesta de upload exitoso:**

```json
{
  "id": "MLU-12345678-XXXX",
  "max_size": "1200x1200",
  "dominant_color": "#3B7BBF",
  "quality": "",
  "variations": {
    "F": "https://http2.mlstatic.com/D_NQ_NP_12345.jpg",
    "O": "https://http2.mlstatic.com/D_NQ_NP_12345-O.jpg",
    "V": "https://http2.mlstatic.com/D_NQ_NP_12345-V.jpg"
  }
}
```

### 4.2 Requisitos Técnicos de Imágenes

| Parámetro | Valor |
|---|---|
| Formatos aceptados | JPG, JPEG, PNG |
| Tamaño máximo de archivo | 10 MB |
| Dimensión mínima | 500 x 500 px |
| Dimensión máxima procesada | 1920 x 1920 px |
| Dimensión recomendada | 1200 x 1200 px |
| Espacio de color | RGB (mejor que CMYK) |
| Cantidad máxima | Varía por categoría (`max_pictures_per_item` en la respuesta de la categoría) |

### 4.3 Agregar/Actualizar Fotos en un Ítem Existente

```python
def update_pictures(item_id: str, picture_ids: list, access_token: str):
    """
    Reemplaza las fotos de un ítem activo.
    picture_ids es una lista de dicts: [{"id": "MLU-xxx"}, ...]
    """
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"pictures": picture_ids}
    
    response = requests.put(url, json=payload, headers=headers)
    # HTTP 200 con {} vacío en caso de éxito
    return response.status_code == 200
```

---

## 5. Descripción del Ítem

La descripción es un campo especial que se gestiona por un endpoint separado. Soporta únicamente texto plano (no HTML, no markdown, no negrita). Los saltos de línea se hacen con `\n`.

### 5.1 Agregar Descripción (POST — solo una vez)

```python
def add_description(item_id: str, text: str, access_token: str) -> bool:
    """
    Agrega la descripción a un ítem recién creado.
    Solo se puede llamar una vez. Para modificar, usar update_description().
    """
    url = f"https://api.mercadolibre.com/items/{item_id}/description"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"plain_text": text}
    
    response = requests.post(url, json=payload, headers=headers)
    return response.status_code == 201

descripcion = (
    "Bavaria 37 año 2015 en excelente estado.\n"
    "Motor Volvo Penta 75HP.\n"
    "Eslora: 11.30m — Manga: 3.67m — Calado: 1.85m\n"
    "3 camarotes, 1 baño, cocina completa.\n"
    "Se puede ver en Club Náutico Montevideo.\n"
    "No tiene deudas. Título al día.\n"
    "Consultas: acepto propuestas serias."
)

add_description("MLU1234567890", descripcion, access_token)
```

### 5.2 Actualizar Descripción (PUT)

```python
def update_description(item_id: str, new_text: str, access_token: str) -> bool:
    url = f"https://api.mercadolibre.com/items/{item_id}/description"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"plain_text": new_text}
    
    response = requests.put(url, json=payload, headers=headers)
    return response.status_code == 200
```

---

## 6. Tipos de Publicación (listing_type_id)

### 6.1 Tipos Disponibles por Sitio

**MLU — Uruguay (desde noviembre 2023):**

| listing_type_id | Nombre comercial | Costo | Visibilidad |
|---|---|---|---|
| `free` | Gratis | Sin costo | Baja |
| `gold_special` | Premium | Comisión sobre venta | Alta (destacada) |

Desde noviembre 2023, en Uruguay solo están habilitados `free` y `gold_special`. Los tipos `gold`, `silver`, `bronze` fueron discontinuados.

**MLA — Argentina:**

| listing_type_id | Nombre comercial | Características |
|---|---|---|
| `free` | Gratuita | Sin costo, baja exposición |
| `bronze` | Bronce | Bajo costo fijo |
| `silver` | Plata | Exposición media |
| `gold` | Oro | Alta exposición |
| `gold_special` | Clásica | Comisión, sin costo de cuotas extra |
| `gold_premium` | Premium / Oro Premium | Máxima exposición |
| `gold_pro` | Premium Pro | Cuotas mejoradas, mayor costo |

**Nota Argentina (2024-2025):** En MLA, actualmente solo `gold_special` (Clásica) está habilitado para la mayoría de las categorías de marketplace convencional.

### 6.2 Consultar Tipos Disponibles por Categoría

```python
def get_listing_types(category_id: str, site_id: str = "MLU") -> list:
    url = f"https://api.mercadolibre.com/categories/{category_id}/listing_types"
    # Este endpoint no requiere autenticación
    response = requests.get(url)
    return response.json()

# Consultar qué tipos están disponibles para embarcaciones en Uruguay
tipos = get_listing_types("MLU109890", "MLU")
```

### 6.3 Consultar Precios de Publicación

```python
def get_listing_fees(site_id: str, category_id: str, price: float) -> dict:
    """
    Devuelve las comisiones de cada listing_type para el precio dado.
    """
    url = (
        f"https://api.mercadolibre.com/sites/{site_id}/listing_prices"
        f"?price={price}&category_id={category_id}"
    )
    response = requests.get(url)
    return response.json()

fees = get_listing_fees("MLU", "MLU109890", 85000)
```

---

## 7. Categorías para Embarcaciones — MLU y MLA

### 7.1 Árbol de Categorías de Náutica

Las categorías de náutica en MELI se ubican dentro de la rama de **Vehículos**. La jerarquía general es:

```
Autos, Motos y Otros (raíz de vehículos)
  └── Náutica
        ├── Lanchas
        ├── Veleros
        ├── Botes
        ├── Motos de Agua
        ├── Accesorios Náuticos
        └── Motores Náuticos
```

### 7.2 IDs de Categorías — MLU (Uruguay)

La categoría raíz de náutica en MLU tiene el ID visible `MLU1785` (identificador en la URL de tendencias `tendencias.mercadolibre.com.uy/1785-nautica`).

**Para obtener el árbol completo sin autenticación:**

```python
def get_categories(site_id: str = "MLU") -> list:
    """Obtiene la lista de categorías raíz del sitio."""
    url = f"https://api.mercadolibre.com/sites/{site_id}/categories"
    response = requests.get(url)
    return response.json()

def get_category_children(category_id: str) -> dict:
    """Obtiene hijos y detalles de una categoría específica."""
    url = f"https://api.mercadolibre.com/categories/{category_id}"
    response = requests.get(url)
    return response.json()

# Explorar árbol de náutica en Uruguay
nautica_mlu = get_category_children("MLU1785")
for child in nautica_mlu.get("children_categories", []):
    print(f"  {child['id']} — {child['name']}")
```

**Subcategorías conocidas de náutica MLU (Uruguay):**

| Subcategoría | URL de referencia | Nota |
|---|---|---|
| Lanchas | `/nautica/lanchas/` | Lanchas a motor |
| Veleros | `/nautica/veleros/` | Veleros y cruceros |
| Botes | `/nautica/botes/` | Botes pequeños, inflables |
| Motos de Agua | `/nautica/motos-agua/` | Jet ski, motos acuáticas |
| Motores Náuticos | (dentro de náutica) | Motores fuera de borda |
| Accesorios Náuticos | (dentro de náutica) | Accesorios varios |

**Nota:** Los IDs numéricos completos (ej. `MLU109890`) deben verificarse haciendo un GET a `https://api.mercadolibre.com/sites/MLU/categories` y navegando el árbol, ya que MELI puede reorganizar categorías. El proceso de verificación se describe en la sección 7.4.

### 7.3 IDs de Categorías — MLA (Argentina)

**Árbol de náutica MLA:**

| Categoría | Ruta observable | Nota |
|---|---|---|
| Náutica (raíz) | `/nautica/` | Categoría padre |
| Embarcaciones a Vela | `/nautica/embarcaciones-vela/` | Veleros, cruceros |
| Lanchas | `/nautica/lanchas/` | Lanchas a motor |
| Motores Náuticos | `/nautica/motores-nauticos/` | Motores fuera de borda |
| Accesorios Náuticos | Dentro del árbol de náutica | |

**Consultar precios de publicación para MLA náutica:**

```
GET https://api.mercadolibre.com/sites/MLA/listing_prices?price=5000&category_id=MLA1744
```

(MLA1744 es referencia de ejemplo de la documentación oficial; verificar el ID correcto con el tree dump.)

### 7.4 Proceso Recomendado para Encontrar el category_id Correcto

**Opción A — Category Predictor:**

```python
def predict_category(title: str, site_id: str = "MLU") -> list:
    """
    Predice la categoría basándose en el título del producto.
    Límite: 400 requests/minuto.
    El título puede estar en español para MLU/MLA.
    """
    url = f"https://api.mercadolibre.com/sites/{site_id}/domain_discovery/search"
    params = {"q": title, "limit": 5}
    response = requests.get(url, params=params)
    return response.json()

# Ejemplo para un velero
predicciones = predict_category("Bavaria 37 velero eslora 11m", "MLU")
for p in predicciones:
    print(f"  category_id: {p.get('category_id')} — {p.get('category_name')}")
    print(f"  domain_id: {p.get('domain_id')}")
```

**Opción B — Descargar el árbol completo de categorías:**

```python
import gzip
import json

def download_category_tree(site_id: str, access_token: str) -> list:
    """
    Descarga el árbol completo de categorías con atributos.
    Respuesta comprimida en gzip.
    """
    url = f"https://api.mercadolibre.com/sites/{site_id}/categories/all"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept-Encoding": "gzip",
    }
    response = requests.get(url, headers=headers, stream=True)
    
    # La respuesta viene comprimida
    content = gzip.decompress(response.content)
    return json.loads(content)
```

**Opción C — Navegar la UI y extraer el category_id de la URL del listado activo:**

Ir a un ítem publicado en MELI Uruguay de la categoría deseada, abrir la ficha y usar la API de items para ver su `category_id`:

```python
# Ejemplo: un ítem público de velero en MLU
response = requests.get("https://api.mercadolibre.com/items/MLU-715019676")
print(response.json().get("category_id"))
```

---

## 8. Atributos Requeridos por Categoría

Los atributos requeridos varían según la categoría. Omitir un atributo marcado como `required` genera un error `400` al crear el ítem.

### 8.1 Consultar Atributos de una Categoría

```python
def get_category_attributes(category_id: str) -> list:
    """
    Devuelve todos los atributos de la categoría con sus reglas.
    No requiere autenticación.
    """
    url = f"https://api.mercadolibre.com/categories/{category_id}/attributes"
    response = requests.get(url)
    return response.json()

attrs = get_category_attributes("MLU109890")  # usar el ID real de lanchas/veleros
for attr in attrs:
    required = "REQUERIDO" if attr.get("tags", {}).get("required") else "opcional"
    print(f"  {attr['id']} — {attr['name']} [{required}]")
    if attr.get("values"):
        for v in attr["values"][:3]:
            print(f"    value_id: {v['id']} — {v['name']}")
```

### 8.2 Atributos Típicos para Embarcaciones (Náutica)

Basado en la estructura estándar de MELI para categorías de náutica:

| Atributo ID | Nombre | Tipo | Obligatorio típico |
|---|---|---|---|
| `BOAT_YEAR` | Año del barco | Número (año) | Sí |
| `BRAND` | Marca | String/Enum | Sí |
| `MODEL` | Modelo | String | Sí |
| `TOTAL_LENGTH` | Eslora | Número + unidad (m/ft) | Sí |
| `BEAM` | Manga | Número + unidad | No |
| `DRAFT` | Calado | Número + unidad | No |
| `ENGINE_TYPE` | Tipo de motor | Enum | Sí |
| `FUEL_TYPE` | Tipo de combustible | Enum | No |
| `ENGINE_POWER` | Potencia del motor | Número + unidad | No |
| `CABINS_QUANTITY` | Cantidad de camarotes | Número | No |
| `VEHICLE_CONDITION` | Condición del vehículo | Enum | Sí |
| `SELLER_TYPE` | Tipo de vendedor | Enum | Depende |
| `DISPLACEMENT` | Desplazamiento | Número + unidad | No |
| `MAST_TYPE` | Tipo de mástil (veleros) | Enum | No |

**Nota:** Los IDs exactos de atributos y sus `value_id` permitidos pueden variar. Siempre consultar `GET /categories/{id}/attributes` para la categoría específica antes de publicar.

### 8.3 Estructura de un Atributo con value_struct (Medidas)

```json
{
  "id": "TOTAL_LENGTH",
  "value_name": "11",
  "value_struct": {
    "number": 11,
    "unit": "m"
  }
}
```

### 8.4 Estructura de un Atributo Enumerado

```json
{
  "id": "ENGINE_TYPE",
  "value_id": "229873",
  "value_name": "Motor a vela"
}
```

Para encontrar los `value_id` disponibles, el endpoint de atributos devuelve los valores posibles:

```json
{
  "id": "ENGINE_TYPE",
  "name": "Tipo de motor",
  "type": "list",
  "values": [
    {"id": "229873", "name": "Motor a vela"},
    {"id": "229874", "name": "Motor fuera de borda"},
    {"id": "229875", "name": "Motor de centro"},
    {"id": "229876", "name": "Motor diesel"}
  ]
}
```

---

## 9. Gestión de Publicaciones

### 9.1 Consultar Estado de una Publicación

```python
def get_item(item_id: str, access_token: str) -> dict:
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

item = get_item("MLU1234567890", access_token)
print(f"Estado: {item['status']}")  # active, paused, closed
print(f"Precio: {item['price']} {item['currency_id']}")
```

**Posibles valores de `status`:**

| Status | Descripción |
|---|---|
| `active` | Publicación activa y visible |
| `paused` | Pausada manualmente, no visible |
| `closed` | Cerrada (no se puede reactivar, solo relistar) |
| `under_review` | En revisión por MELI |
| `payment_required` | Requiere pago para activarse |
| `inactive` | Inactiva por otras razones |

### 9.2 Actualizar Precio

```python
def update_price(item_id: str, new_price: float, access_token: str) -> bool:
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"price": new_price}
    
    response = requests.put(url, json=payload, headers=headers)
    # Éxito: HTTP 200 con {} vacío
    return response.status_code == 200

update_price("MLU1234567890", 82000, access_token)
```

### 9.3 Actualizar Título, Descripción u Otros Campos

```python
def update_item(item_id: str, fields: dict, access_token: str) -> bool:
    """
    Actualiza uno o más campos de un ítem activo.
    No todos los campos son actualizables (depende de si tuvo ventas).
    """
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.put(url, json=fields, headers=headers)
    return response.status_code == 200

# Actualizar título y precio a la vez
update_item(
    "MLU1234567890",
    {"title": "Velero Bavaria 37 2015 - PRECIO REBAJADO", "price": 79000},
    access_token
)
```

### 9.4 Pausar una Publicación

```python
def pause_item(item_id: str, access_token: str) -> bool:
    """
    Pausa la publicación. No es visible pero no se cierra.
    Se puede reactivar con status 'active'.
    """
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"status": "paused"}
    response = requests.put(url, json=payload, headers=headers)
    return response.status_code == 200
```

### 9.5 Reactivar una Publicación Pausada

```python
def reactivate_item(item_id: str, access_token: str) -> bool:
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"status": "active"}
    response = requests.put(url, json=payload, headers=headers)
    return response.status_code == 200
```

### 9.6 Cerrar una Publicación

```python
def close_item(item_id: str, access_token: str) -> bool:
    """
    Cierra definitivamente. No se puede reactivar, solo relistar.
    """
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"status": "closed"}
    response = requests.put(url, json=payload, headers=headers)
    return response.status_code == 200
```

### 9.7 Relistar una Publicación Cerrada (Relist)

Al relistar se crea un **nuevo ítem** heredando visitas, preguntas y ventas del original (si el relist se hace dentro de los 60 días del cierre).

```python
def relist_item(
    closed_item_id: str,
    new_price: float,
    listing_type_id: str,
    available_quantity: int,
    access_token: str
) -> dict:
    """
    Crea una nueva publicación basada en un ítem cerrado.
    Retorna el nuevo ítem con su nuevo item_id.
    """
    url = f"https://api.mercadolibre.com/items/{closed_item_id}/relist"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "price": new_price,
        "quantity": available_quantity,
        "listing_type_id": listing_type_id,
    }
    
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

nuevo_item = relist_item("MLU1234567890", 80000, "gold_special", 1, access_token)
print(f"Nuevo item_id: {nuevo_item['id']}")
```

---

## 10. Preguntas y Respuestas

### 10.1 Consultar Preguntas de un Ítem

```python
def get_questions(item_id: str, access_token: str, status: str = None) -> dict:
    """
    Obtiene preguntas de un ítem.
    status puede ser: 'unanswered', 'answered', 'closed_unanswered', 'deleted'
    """
    url = "https://api.mercadolibre.com/marketplace/questions/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"item_id": item_id}
    if status:
        params["status"] = status
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

preguntas = get_questions("MLU1234567890", access_token, status="unanswered")
for q in preguntas.get("questions", []):
    print(f"[{q['id']}] {q['from']['nickname']}: {q['text']}")
```

**Respuesta:**

```json
{
  "total": 3,
  "limit": 50,
  "questions": [
    {
      "id": 5678901234,
      "seller_id": 987654321,
      "text": "¿El motor fue revisado recientemente?",
      "status": "unanswered",
      "date_created": "2026-04-25T14:30:00.000Z",
      "item_id": "MLU1234567890",
      "from": {
        "id": 111222333,
        "nickname": "COMPRADOR_UY"
      },
      "answer": null
    }
  ]
}
```

### 10.2 Responder una Pregunta

```python
def answer_question(question_id: int, answer_text: str, access_token: str) -> bool:
    url = "https://api.mercadolibre.com/answers"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "question_id": question_id,
        "text": answer_text,
    }
    
    response = requests.post(url, json=payload, headers=headers)
    return response.status_code in (200, 201)

answer_question(
    5678901234,
    "Sí, el motor fue revisado en enero 2026 por taller autorizado Volvo Penta.",
    access_token
)
```

### 10.3 Consultar Preguntas por Vendedor

```python
def get_questions_by_seller(seller_id: int, access_token: str) -> dict:
    url = "https://api.mercadolibre.com/marketplace/questions/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"seller_id": seller_id, "status": "unanswered"}
    
    response = requests.get(url, headers=headers, params=params)
    return response.json()
```

---

## 11. Webhooks y Notificaciones

### 11.1 Tópicos Disponibles

| Tópico | Descripción |
|---|---|
| `items` | Cambios en publicaciones (precio, estado, etc.) |
| `questions` | Preguntas nuevas o respondidas |
| `orders_v2` | Creación y cambios en órdenes de venta |
| `payments` | Creación y cambios de estado de pagos |
| `messages` | Mensajes entre comprador y vendedor |
| `shipments` | Cambios en envíos |
| `claims` | Reclamos post-venta |
| `orders_feedback` | Calificaciones de compradores |
| `items_prices` | Cambios de precios |
| `stock_locations` | Cambios de stock |

### 11.2 Suscripción a Notificaciones

Las notificaciones se configuran en el portal de developers al momento de crear/editar la aplicación, indicando la **Notification URL** (callback). También se puede hacer por API:

```python
def subscribe_to_notifications(
    app_id: str,
    topic: str,
    callback_url: str,
    user_id: int,
    access_token: str
) -> dict:
    url = f"https://api.mercadolibre.com/applications/{app_id}/webhooks"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "topic": topic,
        "callback_url": callback_url,
        "user_id": user_id,
    }
    
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

subscribe_to_notifications(
    app_id="123456789",
    topic="questions",
    callback_url="https://mg-nautica.com/webhooks/meli",
    user_id=987654321,
    access_token=access_token
)
```

### 11.3 Estructura del Payload de Notificación (POST inbound)

Cuando ocurre un evento, MELI envía un `POST` a tu callback URL:

```json
{
  "resource": "/items/MLU1234567890",
  "user_id": 987654321,
  "topic": "items",
  "application_id": 123456789,
  "attempts": 1,
  "sent": "2026-04-26T12:00:00.000Z",
  "_id": "2e2f4bc0-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

Para preguntas:

```json
{
  "resource": "/questions/5678901234",
  "user_id": 987654321,
  "topic": "questions",
  "application_id": 123456789,
  "attempts": 1,
  "sent": "2026-04-26T12:00:00.000Z",
  "_id": "3f3a5cd1-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**Importante:** La notificación solo contiene la referencia al recurso, no el detalle completo. Hay que hacer un GET al recurso indicado para obtener los datos:

```python
# En el webhook handler de Flask
@app.route("/webhooks/meli", methods=["POST"])
def meli_webhook():
    data = request.json
    topic = data.get("topic")
    resource = data.get("resource")      # e.g. "/questions/5678901234"
    user_id = data.get("user_id")
    
    # Responder 200 inmediatamente (MELI reintenta si no hay respuesta rápida)
    # Procesar en background (Celery, RQ, threading, etc.)
    process_notification.delay(topic, resource, user_id)
    
    return "", 200
```

### 11.4 Validación de Notificaciones con x-signature

MELI firma las notificaciones con una clave secreta. La firma viene en el header `x-signature`:

```
x-signature: ts=1234567890,v1=abc123def456...
```

**Validación con HMAC-SHA256:**

```python
import hmac
import hashlib

MELI_SECRET = "TU_CLIENT_SECRET_O_WEBHOOK_SECRET"

def validate_meli_signature(
    request_headers: dict,
    data_id: str,
    x_request_id: str
) -> bool:
    """
    Valida que la notificación proviene de MELI usando HMAC-SHA256.
    """
    x_signature = request_headers.get("x-signature", "")
    
    # Parsear ts y v1 del header
    parts = dict(part.split("=", 1) for part in x_signature.split(","))
    ts = parts.get("ts", "")
    v1_received = parts.get("v1", "")
    
    # Construir el mensaje a firmar
    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    
    # Calcular HMAC
    signature = hmac.new(
        MELI_SECRET.encode("utf-8"),
        manifest.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, v1_received)

# En el handler Flask:
@app.route("/webhooks/meli", methods=["POST"])
def meli_webhook():
    data = request.json
    data_id = request.args.get("data.id", "")
    x_request_id = request.headers.get("x-request-id", "")
    
    if not validate_meli_signature(dict(request.headers), data_id, x_request_id):
        return "Unauthorized", 401
    
    # Procesar la notificación...
    return "", 200
```

### 11.5 Reintentos de MELI

Si tu endpoint no responde con HTTP 200 dentro de un tiempo límite, MELI reintentará la notificación con backoff exponencial. El campo `attempts` en el payload indica cuántos intentos se han realizado. Responder siempre 200 lo antes posible y procesar el evento de forma asíncrona.

---

## 12. Rate Limits y Manejo de Errores

### 12.1 Límites de Rate

| Límite | Valor | Nota |
|---|---|---|
| Requests por minuto (por vendedor) | 1.500 | Devuelve HTTP 429 si se excede |
| Requests del Category Predictor | 400 por minuto | Endpoint específico |
| Listings simultáneos (por reputación) | 1.000 – 50.000 | Depende del nivel del vendedor |

Al superar el rate limit, la API devuelve:

```
HTTP 429 Too Many Requests
(body vacío)
```

### 12.2 Códigos de Error HTTP

| Código | Significado | Acción |
|---|---|---|
| `200` | OK (GET/PUT exitoso) | Procesar respuesta |
| `201` | Created (POST exitoso) | Guardar ID del recurso creado |
| `400` | Bad Request | Revisar JSON, campos requeridos, formato |
| `401` | Unauthorized | Refrescar token o re-autorizar |
| `403` | Forbidden | El token no tiene el scope necesario o falta permiso |
| `404` | Not Found | El recurso no existe o el ID es incorrecto |
| `409` | Conflict | Conflicto de estado (ej: pausar un ítem ya pausado) |
| `429` | Too Many Requests | Esperar y reintentar con backoff |
| `500` | Internal Server Error | Error en MELI, reintentar después |

### 12.3 Estructura de Error 400

```json
{
  "message": "invalid category_id",
  "error": "bad_request",
  "status": 400,
  "cause": [
    {
      "code": 112,
      "description": "The category cannot be used to list",
      "data": null
    }
  ]
}
```

### 12.4 Cliente HTTP con Retry y Backoff Exponencial

```python
import requests
import time
import random
from functools import wraps

class MeliAPIError(Exception):
    def __init__(self, status_code, message, cause=None):
        self.status_code = status_code
        self.message = message
        self.cause = cause
        super().__init__(f"HTTP {status_code}: {message}")

class MeliAuthError(MeliAPIError):
    pass

class MeliRateLimitError(MeliAPIError):
    pass


def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator para reintentar llamadas con backoff exponencial + jitter.
    Reintenta solo en errores 429 y 5xx.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except MeliRateLimitError as e:
                    last_exception = e
                    if attempt < max_retries:
                        # Backoff exponencial con jitter
                        delay = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
                        time.sleep(delay)
                except MeliAPIError as e:
                    if e.status_code >= 500 and attempt < max_retries:
                        last_exception = e
                        delay = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
                        time.sleep(delay)
                    else:
                        raise
            raise last_exception
        return wrapper
    return decorator


class MeliClient:
    BASE_URL = "https://api.mercadolibre.com"
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
    
    def _handle_response(self, response: requests.Response) -> dict:
        if response.status_code == 401:
            raise MeliAuthError(401, "Token expirado o inválido")
        if response.status_code == 403:
            raise MeliAuthError(403, "Permiso denegado (scope insuficiente)")
        if response.status_code == 429:
            raise MeliRateLimitError(429, "Rate limit excedido")
        if response.status_code >= 400:
            try:
                body = response.json()
                msg = body.get("message", "Error desconocido")
                cause = body.get("cause", [])
            except Exception:
                msg = response.text
                cause = []
            raise MeliAPIError(response.status_code, msg, cause)
        
        if response.text:
            return response.json()
        return {}
    
    @with_retry(max_retries=3, base_delay=2.0)
    def get(self, path: str, params: dict = None) -> dict:
        response = self.session.get(f"{self.BASE_URL}{path}", params=params)
        return self._handle_response(response)
    
    @with_retry(max_retries=3, base_delay=2.0)
    def post(self, path: str, data: dict) -> dict:
        response = self.session.post(f"{self.BASE_URL}{path}", json=data)
        return self._handle_response(response)
    
    @with_retry(max_retries=3, base_delay=2.0)
    def put(self, path: str, data: dict) -> dict:
        response = self.session.put(f"{self.BASE_URL}{path}", json=data)
        return self._handle_response(response)


# Uso:
client = MeliClient(access_token)
item = client.get("/items/MLU1234567890")
```

---

## 13. Sandbox y Testing

### 13.1 No Existe un Sandbox Real

**Mercado Libre no tiene un entorno sandbox separado.** Las pruebas se realizan directamente en producción usando **usuarios de prueba** (test users). Los test users pueden:
- Publicar ítems
- Realizar compras simuladas
- Hacer preguntas entre ellos

**Los test users solo pueden interactuar entre sí.** Un test user no puede comprar ítems de vendedores reales ni viceversa.

### 13.2 Crear un Usuario de Prueba

```python
def create_test_user(site_id: str, access_token: str) -> dict:
    """
    Crea un usuario de prueba para el sitio indicado.
    Límite: máximo 10 test users por cuenta de developer.
    Guardar las credenciales porque no se pueden recuperar después.
    """
    url = "https://api.mercadolibre.com/users/test_user"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"site_id": site_id}
    
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

# Crear test user para Uruguay
test_user_mlu = create_test_user("MLU", access_token)
print(test_user_mlu)
```

**Respuesta:**

```json
{
  "id": 123456,
  "nickname": "TETE1234567",
  "password": "qatest1234",
  "site_status": "active",
  "email": "test_user_123456@testuser.com"
}
```

**Guardar estos datos de forma segura.** No hay endpoint para listar los test users creados.

### 13.3 Limitaciones de los Test Users

- Máximo **10 test users** por cuenta de developer.
- Los test users expiran después de un período de inactividad.
- Solo pueden comprar/vender ítems de otros test users.
- No pueden recibir pagos reales.
- Las publicaciones de test users aparecen en el buscador real de MELI (usar títulos que indiquen claramente que son de prueba, ej. "TEST - No Ofertar").

### 13.4 Flujo de Testing Recomendado

```python
# 1. Con el access_token del test user VENDEDOR, crear un ítem
vendedor_token = exchange_code_for_tokens(auth_code_vendedor)["access_token"]

test_item = {
    "title": "TEST NO OFERTAR - Velero Bavaria 37",
    "category_id": "MLU109890",
    "price": 1,          # precio mínimo para test
    "currency_id": "UYU",
    "available_quantity": 1,
    "buying_mode": "buy_it_now",
    "listing_type_id": "free",
    "condition": "used",
}

item_response = create_listing(test_item, vendedor_token)
test_item_id = item_response["id"]

# 2. Con el access_token del test user COMPRADOR, hacer una pregunta
comprador_token = exchange_code_for_tokens(auth_code_comprador)["access_token"]

pregunta_url = "https://api.mercadolibre.com/questions"
pregunta = {
    "text": "¿El artículo está disponible?",
    "item_id": test_item_id
}
requests.post(pregunta_url, json=pregunta, 
              headers={"Authorization": f"Bearer {comprador_token}"})

# 3. Verificar que el webhook fue recibido en tu endpoint
# 4. Con el token del vendedor, responder la pregunta
```

### 13.5 Sitios Soportados para Test Users

Los sitios confirmados para creación de test users incluyen: MLA (Argentina), MLB (Brasil), MLC (Chile), MCO (Colombia), MLM (México), MPE (Perú). Para MLU (Uruguay), el proceso es análogo pero verificar disponibilidad con `site_id: "MLU"`.

---

## 14. Ejemplo Completo: Publicar un Velero en MLU con Precio en USD

Este ejemplo integra todos los pasos anteriores para publicar un velero en Mercado Libre Uruguay.

```python
import requests
import time

# ============================================================
# CONFIGURACIÓN
# ============================================================
APP_ID = "TU_CLIENT_ID"
APP_SECRET = "TU_CLIENT_SECRET"
REDIRECT_URI = "https://mg-nautica.com/auth/callback"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

# El access_token debe obtenerse previamente via OAuth 2.0 flow
# (ver sección 2.3)
ACCESS_TOKEN = "APP_USR-OBTENIDO-VIA-OAUTH..."


# ============================================================
# PASO 1: Encontrar el category_id correcto para veleros en MLU
# ============================================================

def find_velero_category():
    """
    Usar el category predictor para encontrar el category_id de veleros en MLU.
    """
    url = "https://api.mercadolibre.com/sites/MLU/domain_discovery/search"
    params = {"q": "velero Bavaria 37 eslora 11 metros", "limit": 5}
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        predictions = response.json()
        for p in predictions:
            print(f"  → category_id: {p.get('category_id')} | {p.get('category_name')}")
            print(f"    domain_id: {p.get('domain_id')}")
        return predictions[0].get("category_id") if predictions else None
    return None

# En producción, esto retorna algo como "MLU109XXX" (verificar el ID real)
# Para este ejemplo usamos el ID que la predicción devuelva
category_id_veleros = find_velero_category()
print(f"Category ID para veleros MLU: {category_id_veleros}")


# ============================================================
# PASO 2: Consultar atributos requeridos
# ============================================================

def get_required_attributes(category_id: str) -> list:
    url = f"https://api.mercadolibre.com/categories/{category_id}/attributes"
    response = requests.get(url)
    return [
        attr for attr in response.json()
        if attr.get("tags", {}).get("required", False)
    ]

required_attrs = get_required_attributes(category_id_veleros)
print(f"\nAtributos requeridos para {category_id_veleros}:")
for attr in required_attrs:
    print(f"  - {attr['id']}: {attr['name']}")


# ============================================================
# PASO 3: Subir fotos del velero
# ============================================================

def upload_photo_from_url(photo_url: str, access_token: str) -> str:
    """
    Descarga la foto de storage propio y la sube a MELI.
    Alternativa: incluir la URL directamente en 'pictures'.
    """
    # Descargar la imagen de nuestro storage
    img_response = requests.get(photo_url)
    img_response.raise_for_status()
    
    upload_url = "https://api.mercadolibre.com/pictures/items/upload"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Determinar content-type
    content_type = img_response.headers.get("content-type", "image/jpeg")
    files = {
        "file": ("photo.jpg", img_response.content, content_type)
    }
    
    response = requests.post(upload_url, headers=headers, files=files)
    response.raise_for_status()
    return response.json()["id"]

# URLs de las fotos del barco en nuestro storage
fotos_urls = [
    "https://storage.mg-nautica.com/boats/bavaria-37-exterior.jpg",
    "https://storage.mg-nautica.com/boats/bavaria-37-interior.jpg",
    "https://storage.mg-nautica.com/boats/bavaria-37-cockpit.jpg",
]

picture_ids = []
for url in fotos_urls:
    try:
        pid = upload_photo_from_url(url, ACCESS_TOKEN)
        picture_ids.append({"id": pid})
        print(f"Foto subida: {pid}")
        time.sleep(0.5)  # pequeña pausa entre uploads
    except Exception as e:
        print(f"Error subiendo foto {url}: {e}")
        # Fallback: usar URL directa
        picture_ids.append({"source": url})


# ============================================================
# PASO 4: Construir el payload del ítem
# ============================================================

# Datos del barco desde el modelo de mg-nautica-web
barco = {
    "slug": "bavaria-37-2015-velero-mlu",
    "title": "Velero Bavaria 37 2015 - Eslora 11.3m - Motor Diesel",
    "description": (
        "Bavaria 37 año 2015 en excelente estado general.\n"
        "Motor Volvo Penta MD2030 75HP, revisado enero 2026.\n"
        "Eslora: 11.30m — Manga: 3.67m — Calado: 1.85m\n"
        "3 camarotes, 1 baño con ducha, cocina completa.\n"
        "VHF, GPS Garmin, autopiloto, radar.\n"
        "Se encuentra en Club Náutico Montevideo.\n"
        "Título limpio, sin deudas. Listo para navegar.\n"
        "Precio a convenir. Acepto propuestas serias."
    ),
    "price_usd": 85000,
    "boat_type": "velero",
    "flag": "UY",
    "specs": {
        "eslora_m": 11.3,
        "manga_m": 3.67,
        "calado_m": 1.85,
        "motor": "Volvo Penta MD2030",
        "hp": 75,
        "cabinas": 3,
        "year": 2015,
    }
}

item_payload = {
    # === CAMPOS BASE ===
    "title": barco["title"][:60],  # MELI tiene límite de caracteres en el título
    "category_id": category_id_veleros,
    "price": barco["price_usd"],
    "currency_id": "USD",
    "available_quantity": 1,
    "buying_mode": "buy_it_now",
    "listing_type_id": "gold_special",  # Premium (único no-gratuito en MLU)
    "condition": "used",
    
    # === FOTOS ===
    "pictures": picture_ids,
    
    # === ATRIBUTOS (completar con los IDs reales devueltos por el endpoint) ===
    "attributes": [
        {
            "id": "BOAT_YEAR",
            "value_name": str(barco["specs"]["year"])
        },
        {
            "id": "BRAND",
            "value_name": "Bavaria"
        },
        {
            "id": "MODEL",
            "value_name": "Bavaria 37"
        },
        {
            "id": "TOTAL_LENGTH",
            "value_name": str(barco["specs"]["eslora_m"]),
            "value_struct": {
                "number": barco["specs"]["eslora_m"],
                "unit": "m"
            }
        },
        {
            "id": "FUEL_TYPE",
            "value_name": "Diesel"
        },
        {
            "id": "CABINS_QUANTITY",
            "value_name": str(barco["specs"]["cabinas"])
        },
        {
            "id": "VEHICLE_CONDITION",
            "value_id": "2230581",  # "Usado" — verificar este value_id para la categoría
            "value_name": "Usado"
        },
    ],
}


# ============================================================
# PASO 5: Crear la publicación
# ============================================================

def create_velero_listing(payload: dict, access_token: str) -> dict:
    url = "https://api.mercadolibre.com/items"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 201:
        result = response.json()
        print(f"\n✓ Publicación creada exitosamente!")
        print(f"  Item ID: {result['id']}")
        print(f"  URL: {result['permalink']}")
        print(f"  Estado: {result['status']}")
        return result
    else:
        print(f"\n✗ Error al crear publicación: HTTP {response.status_code}")
        print(f"  {response.json()}")
        response.raise_for_status()

item_creado = create_velero_listing(item_payload, ACCESS_TOKEN)


# ============================================================
# PASO 6: Agregar descripción larga (endpoint separado)
# ============================================================

def add_description(item_id: str, description: str, access_token: str) -> bool:
    url = f"https://api.mercadolibre.com/items/{item_id}/description"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"plain_text": description}
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        print(f"✓ Descripción agregada al ítem {item_id}")
        return True
    else:
        print(f"✗ Error al agregar descripción: {response.status_code} — {response.text}")
        return False

add_description(item_creado["id"], barco["description"], ACCESS_TOKEN)

print(f"\n=== PUBLICACIÓN COMPLETADA ===")
print(f"Item ID: {item_creado['id']}")
print(f"URL pública: {item_creado['permalink']}")
```

---

## 15. Mapeo del Modelo de mg-nautica-web a la API de MELI

### 15.1 Tabla de Mapeo de Campos

| Campo mg-nautica-web | Campo MELI API | Notas |
|---|---|---|
| `title` | `title` | Máx ~60 chars en el título principal |
| `description` | `POST /items/{id}/description` → `plain_text` | Endpoint separado, solo texto plano |
| `price_usd` | `price` + `currency_id: "USD"` | Permitido en MLU |
| `boat_type` (velero/lancha) | `category_id` + atributo de tipo | Mapear a category_id correcto |
| `flag` (UY/AR) | `site_id` implícito en el token | No se envía explícitamente |
| `status` (active/sold/etc) | `status` (PUT) | `active`, `paused`, `closed` |
| `photos` (lista de URLs) | `pictures[].source` o `pictures[].id` | Subir primero o usar URL directa |
| `specs.eslora_m` | Atributo `TOTAL_LENGTH` con `value_struct` | Incluir unidad (m) |
| `specs.motor` | Atributo `ENGINE_TYPE` o nombre de motor | Puede ser string o enum |
| `specs.cabinas` | Atributo `CABINS_QUANTITY` | Número como string |
| `slug` | No mapeado directamente | Usar para `seller_sku` si se quiere referencia interna |
| (nuevo) `meli_item_id` | `id` (respuesta) | Guardar en BD para gestión posterior |
| (nuevo) `meli_permalink` | `permalink` (respuesta) | URL pública de la publicación |

### 15.2 Modelo Sugerido para Persistir la Integración

```python
# En el modelo de Boat o en una tabla separada
class BoatMeliListing(db.Model):
    __tablename__ = "boat_meli_listings"
    
    id = db.Column(db.Integer, primary_key=True)
    boat_id = db.Column(db.Integer, db.ForeignKey("boats.id"), nullable=False)
    
    # Datos de la publicación en MELI
    site_id = db.Column(db.String(10), nullable=False)     # "MLU" o "MLA"
    meli_item_id = db.Column(db.String(50), unique=True)   # "MLU1234567890"
    meli_user_id = db.Column(db.Integer)                    # ID del vendedor en MELI
    
    # Estado sincronizado
    status = db.Column(db.String(20), default="active")    # active/paused/closed
    price = db.Column(db.Float)
    currency_id = db.Column(db.String(5))
    
    # Metadatos
    permalink = db.Column(db.String(512))
    category_id = db.Column(db.String(20))
    listing_type_id = db.Column(db.String(20))
    
    # Timestamps
    published_at = db.Column(db.DateTime)
    last_synced_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    boat = db.relationship("Boat", backref="meli_listings")
```

---

## 16. Referencia Rápida de Endpoints

### 16.1 Autenticación

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `https://auth.mercadolibre.com.uy/authorization?...` | Redirect de autorización (MLU) |
| `GET` | `https://auth.mercadolibre.com.ar/authorization?...` | Redirect de autorización (MLA) |
| `POST` | `https://api.mercadolibre.com/oauth/token` | Obtener/refrescar tokens |

### 16.2 Ítems

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/items` | Crear publicación |
| `GET` | `/items/{item_id}` | Consultar publicación |
| `PUT` | `/items/{item_id}` | Actualizar campos (precio, estado, etc.) |
| `POST` | `/items/{item_id}/relist` | Relistar ítem cerrado |
| `POST` | `/items/{item_id}/description` | Agregar descripción |
| `PUT` | `/items/{item_id}/description` | Actualizar descripción |

### 16.3 Imágenes

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/pictures/items/upload` | Subir imagen (multipart/form-data) |

### 16.4 Categorías

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/sites/{site_id}/categories` | Categorías raíz del sitio |
| `GET` | `/categories/{category_id}` | Detalle + hijos de una categoría |
| `GET` | `/categories/{category_id}/attributes` | Atributos y reglas de la categoría |
| `GET` | `/sites/{site_id}/domain_discovery/search?q={title}` | Predictor de categoría |
| `GET` | `/sites/{site_id}/categories/all` | Árbol completo (gzip) |

### 16.5 Preguntas

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/marketplace/questions/search?item_id={id}` | Preguntas de un ítem |
| `GET` | `/marketplace/questions/search?seller_id={id}` | Preguntas de un vendedor |
| `POST` | `/answers` | Responder una pregunta |

### 16.6 Usuarios y Testing

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/users/me` | Datos del usuario autenticado |
| `POST` | `/users/test_user` | Crear usuario de prueba |

### 16.7 Monedas y Sitios

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/sites` | Lista todos los sitios (site_id, nombre, país) |
| `GET` | `/sites/{site_id}/currencies` | Monedas aceptadas por el sitio |
| `GET` | `/currencies/{currency_id}` | Detalle de una moneda |
| `GET` | `/sites/{site_id}/listing_prices?price={p}&category_id={c}` | Tarifas de publicación |

### 16.8 Notificaciones

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/applications/{app_id}/webhooks` | Suscribirse a un tópico |

---

## Notas Finales y Diferencias Clave MLU vs MLA

| Aspecto | MLU (Uruguay) | MLA (Argentina) |
|---|---|---|
| Moneda principal | UYU (pesos uruguayos) | ARS (pesos argentinos) |
| USD permitido | Sí, habitual en embarcaciones | Restricciones cambiarias; verificar |
| Listing types activos | `free`, `gold_special` | `free`, `gold_special` (principalmente) |
| URL de autorización OAuth | `auth.mercadolibre.com.uy` | `auth.mercadolibre.com.ar` |
| Token endpoint | `api.mercadolibre.com/oauth/token` | Mismo (global) |
| Categorías náutica | Árbol propio MLU | Árbol propio MLA |
| Atributos por categoría | Pueden diferir | Pueden diferir |
| Test users | Disponible con site_id "MLU" | Disponible con site_id "MLA" |
| Comisiones de venta | Verificar en portal MELI UY | Verificar en portal MELI AR |

---

**Fuentes consultadas durante la investigación:**

- [Authentication and Authorization - Mercado Libre Developers](https://developers.mercadolibre.com.ar/en_us/authentication-and-authorization)
- [Listing Types and Exposures](https://global-selling.mercadolibre.com/devsite/listing-types-and-exposures)
- [Items & Searches - Global Selling](https://global-selling.mercadolibre.com/devsite/items-and-searches-global-selling)
- [Validate and Upload Pictures](https://global-selling.mercadolibre.com/devsite/pictures)
- [Item Description](https://global-selling.mercadolibre.com/devsite/item-description)
- [Receive Notifications](https://global-selling.mercadolibre.com/devsite/receive-notifications)
- [Categories & Attributes](https://developers.mercadolibre.com.ar/en_us/categories-attributes)
- [Relist Items](https://developers.mercadolibre.com.ar/en_us/relist-items)
- [Start Testing](https://developers.mercadolibre.com.ar/en_us/start-testing)
- [Fees for Listing](https://developers.mercadolibre.com.ar/en_us/fees-for-listing)
- [Rollout - Mercado Libre API Essential Guide](https://rollout.com/integration-guides/mercado-libre/api-essentials)
- [GitHub - mercadolibre/python-sdk](https://github.com/mercadolibre/python-sdk)
- [Authorization and Token Best Practices](https://global-selling.mercadolibre.com/devsite/authorization-and-token-best-practices)

---

Este es el documento técnico completo. A continuación el resumen de lo investigado y producido:

**Lo que se investigó y documentó:**

1. **Autenticación OAuth 2.0** — Flujo completo authorization code, URLs por país (MLU: `auth.mercadolibre.com.uy`, MLA: `auth.mercadolibre.com.ar`), token endpoint global, scopes (`read`, `write`, `offline_access`), expiración de 6 horas del access_token, refresh tokens válidos 6 meses, estrategia de persistencia en Flask.

2. **Publicación de ítems** — Endpoint `POST /items`, estructura JSON completa con todos los campos obligatorios y opcionales, valores de `condition`, `buying_mode`, `currency_id` (USD permitido en MLU para embarcaciones), manejo de `available_quantity=1` para barcos.

3. **Imágenes** — Dos métodos (URL directa vs presubida multipart), endpoint `/pictures/items/upload`, límites (10MB, mínimo 500x500, recomendado 1200x1200), formatos JPG/PNG.

4. **Tipos de publicación** — Desde noviembre 2023, MLU solo tiene `free` y `gold_special`. MLA tiene más opciones. Endpoint para consultar tarifas.

5. **Categorías** — Árbol de náutica en MLU y MLA, process de descubrimiento via category predictor (`/domain_discovery/search`), descarga del árbol completo, cómo obtener atributos requeridos por categoría.

6. **Gestión de publicaciones** — Pausar, reactivar, cerrar, relistar (endpoint `POST /items/{id}/relist`).

7. **Preguntas** — Endpoints de búsqueda por item_id o seller_id, endpoint de respuesta.

8. **Webhooks** — 10+ tópicos soportados, payload de notificación, validación HMAC-SHA256 via `x-signature`, estructura del handler Flask.

9. **Rate limits** — 1.500 requests/minuto, HTTP 429, backoff exponencial con jitter, cliente Python completo con retry decorator.

10. **Testing** — No hay sandbox real; se usan test users (max 10), creación via `POST /users/test_user`, limitaciones de interacción.

11. **Ejemplo completo** — Flujo end-to-end para publicar un velero Bavaria 37 en MLU con precio en USD, incluyendo predicción de categoría, upload de fotos, creación del ítem y adición de descripción.

12. **Mapeo del modelo** — Tabla de correspondencia entre los campos de mg-nautica-web y los campos de la API de MELI, con modelo de BD sugerido para persistir el `meli_item_id`.
agentId: abb8fdb5cf702c834 (use SendMessage with to: 'abb8fdb5cf702c834' to continue this agent)
<usage>total_tokens: 77102
tool_uses: 69
duration_ms: 605895</usage>
