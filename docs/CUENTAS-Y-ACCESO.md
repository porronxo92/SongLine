# Cuentas y acceso: primera entrega

SongLine pasa de sesiones de juego anónimas a cuentas persistentes del anfitrión.
Esta entrega incluye un inicio unificado, registro, login, cierre de sesión, recuperación por
correo configurable y permisos Free aplicados en REST y WebSocket. No activa
compras, cobros ni importación de listas. La autorización musical sigue pendiente;
esta entrega no acredita que la integración pueda comercializarse.

## Reglas vigentes

| Acceso | Equipos | Objetivo para ganar | Catálogo |
|---|---|---|---|
| Free | 2 | De 3 a 5 cartas, contando la inicial | `mix`, «Mix variado» |
| Premium previsto, compra individual de 4,99 € | Hasta 6 | Sin límite comercial; condicionado al catálogo disponible | Mix y dos packs a elegir |

Packs adicionales previstos: 1,99 €. Importación prevista: 2,99 €, hasta 150
canciones. No hay suscripción. La duración de los derechos y la política de
selección de packs deben concretarse antes de vender. Los invitados no necesitan
cuenta. Spotify Premium y SongLine Premium son independientes.

## Navegación

La página `/` muestra el inicio de juego: crear sala y unirse son las dos acciones
centrales. Cuenta, ayuda y planes tienen accesos secundarios. `/jugar` redirige a
`/` para conservar los enlaces anteriores. Si hay una sala guardada, el inicio
ofrece volver a ella sin forzar una redirección automática.

## Identidades

- La sesión de cuenta usa un token aleatorio que caduca a los 30 días. Solo se
  guarda su SHA-256 en PostgreSQL; logout revoca esa sesión.
- Las contraseñas usan PBKDF2-SHA256 con sal aleatoria y 600.000 iteraciones.
- La cuenta y la sesión de juego son distintas. Crear sala usa el bearer de juego
  más `X-Account-Token`; no se aceptan permisos desde el navegador.
- Los permisos de sala se fijan en el servidor al crearla, se guardan en snapshots
  y se comprueban también al cambiar ajustes, empezar y pedir revancha. Una sala
  iniciada conserva sus permisos durante esa sesión.
- No hay endpoint público para activar Premium. `plan` y `pack_slugs` son datos
  administrativos, preparados para el futuro sistema de compras; no constituyen
  un historial de pagos ni acreditan ninguna compra por sí mismos.
- `AUTH_MODE=fake` solo evita Spotify en local; no convierte a un usuario en
  Premium. `ENFORCE_PLAN_LIMITS` es true por defecto; false se usa en pruebas
  aisladas de motor/transporte que cubren todas las configuraciones históricas.

## Neon y Render

La migración `0003` añade `accounts`, `account_sessions` y
`account_password_resets`, sin cambiar ni borrar catálogo ni partidas.
El contenedor ejecuta `alembic upgrade head` antes de arrancar la API. Si la
migración falla, el nuevo proceso no arranca; revisar los logs de Render.

Si Neon contiene tablas creadas manualmente sin historial Alembic, **no ejecutar
`stamp` a ciegas**. Comprobar el esquema contra las migraciones existentes y
reconciliarlo antes de desplegar. La migración se ha probado en PostgreSQL de
pruebas; no se ha accedido directamente al Neon del usuario.

La cuenta requiere PostgreSQL incluso con catálogo CSV o partidas sin
persistencia. Para desarrollo: `make db`, configurar `DATABASE_URL`, ejecutar
`alembic upgrade head` en `apps/server` y arrancar API/web.

## Recuperación de contraseña

Configurar en Render, como secretos cuando corresponda:

- `SMTP_HOST`, `SMTP_PORT` (587 por defecto).
- `SMTP_FROM`: remitente autorizado por el proveedor.
- `SMTP_USERNAME`, `SMTP_PASSWORD`, según proveedor.
- `SMTP_STARTTLS=true` (mantener TLS en producción).
- `PUBLIC_ORIGIN`: URL pública real del frontend en Vercel.

Sin SMTP configurado, la recuperación responde `503 recovery_unavailable`; no
simula enviar correo. Los enlaces caducan a los 30 minutos, se almacenan
hasheados y son de un solo uso. Restablecer invalida todas las sesiones de la
cuenta. La respuesta al solicitar un enlace es genérica para no revelar cuentas.

Esta entrega no verifica la propiedad del correo al registrarse. Antes de abrir
ventas o vincular identidades externas, añadir verificación y no fusionar cuentas
solo por coincidencia del email. Configurar y probar la entrega real de correo
antes de anunciar la recuperación como disponible.

## Siguientes entregas

1. Elección persistente de los dos packs Premium, catálogo de productos y pedidos.
2. Compras simuladas restringidas a pruebas, idempotencia e historial.
3. Importación y validación de listas, con consumo de derechos al completarse.
4. Stripe y cobros reales tras resolver las condiciones de lanzamiento.
