[English](README.md) | [Español](README.es.md)

# NextDNS Blocker

[![PyPI version](https://img.shields.io/pypi/v/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![PyPI downloads](https://img.shields.io/pypi/dm/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![Python versions](https://img.shields.io/pypi/pyversions/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![License](https://img.shields.io/github/license/aristeoibarra/nextdns-blocker)](LICENSE)
[![CI](https://github.com/aristeoibarra/nextdns-blocker/actions/workflows/ci.yml/badge.svg)](https://github.com/aristeoibarra/nextdns-blocker/actions/workflows/ci.yml)
[![Homebrew](https://img.shields.io/badge/homebrew-tap-blue)](https://github.com/aristeoibarra/homebrew-tap)


Sistema automatizado para controlar el acceso a dominios con configuración de horarios por dominio utilizando la API de NextDNS.

## Características

- **Multiplataforma**: Soporte nativo para macOS (launchd), Linux (cron) y Windows (Task Scheduler)
- **Programación por dominio**: Configura horarios de disponibilidad únicos para cada dominio
- **Rangos de tiempo flexibles**: Múltiples ventanas de tiempo por día y diferentes horarios por día de la semana
- **Dominios protegidos**: Marca dominios como protegidos para evitar desbloqueos accidentales
- **Pausar/Reanudar**: Desactiva temporalmente el bloqueo sin cambiar la configuración
- **Sincronización automática**: Se ejecuta cada 2 minutos con protección mediante watchdog
- **Notificaciones de Discord**: Alertas en tiempo real para eventos de bloqueo y desbloqueo
- **Consciente de la zona horaria**: Respeta la zona horaria configurada para la evaluación de horarios
- **Seguro**: Permisos de archivos, validación de entradas y registros de auditoría
- **Integración con la API de NextDNS**: Funciona mediante la denylist de NextDNS
- **Modo dry-run**: Previsualiza los cambios sin aplicarlos
- **Caché inteligente**: Reduce las llamadas a la API mediante caché inteligente de la denylist
- **Limitación de tasa**: Protección integrada contra límites de la API
- **Retroceso exponencial**: Reintentos automáticos con retrasos crecientes en caso de fallos
- **Auto-actualización**: Comando integrado para verificar e instalar actualizaciones

## Requisitos

- Python 3.9+
- Cuenta de NextDNS con API key
- Linux/macOS/Windows

## Instalación
### Opción 1: Homebrew (macOS/Linux)

```bash
brew tap aristeoibarra/tap
brew install nextdns-blocker
Luego ejecuta el asistente de configuración:

bash
Copy code
nextdns-blocker init
Opción 2: Instalar desde PyPI
bash
Copy code
pip install nextdns-blocker
Luego ejecuta el asistente de configuración:

bash
Copy code
nextdns-blocker init
Opción 3: Instalar desde el código fuente
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker
pip install -e .
nextdns-blocker init

Opción 4: Instalación en Windows

En Windows, también puedes usar el instalador de PowerShell:

# Descargar y ejecutar el instalador
irm https://raw.githubusercontent.com/aristeoibarra/nextdns-blocker/main/install.ps1 | iex

# O ejecutarlo localmente después de clonar
.\install.ps1
El instalador:

Verificará la instalación de Python

Instalará el paquete mediante pip

Ejecutará el asistente de configuración interactivo

Configurará el Programador de tareas de Windows para la sincronización automática

Configuración rápida
1. Obtener credenciales de NextDNS

API Key: https://my.nextdns.io/account

Profile ID: Desde la URL (por ejemplo, https://my.nextdns.io/abc123 → abc123)

2. Ejecutar el asistente de configuración
nextdns-blocker init


El asistente solicitará:

API Key

Profile ID
La zona horaria se detecta automáticamente desde tu sistema y se guarda en config.json.

3. Configurar dominios y horarios

Edita config.json en tu directorio de configuración para configurar tus dominios y sus horarios de disponibilidad:

nextdns-blocker config edit


Consulta SCHEDULE_GUIDE.md
 para ver ejemplos detallados de configuración de horarios.

4. Instalar Watchdog (Opcional)

Para la sincronización automática cada 2 minutos:

nextdns-blocker watchdog install
Esto instala tareas programadas específicas de la plataforma:

macOS: trabajos de launchd (~/Library/LaunchAgents/)

Linux: trabajos de cron (crontab -l)

Windows: tareas del Programador de tareas (ver con taskschd.msc)

¡Listo! El sistema ahora se sincronizará automáticamente según los horarios configurados.

##Configuración con Docker

Alternativamente, ejecuta NextDNS Blocker usando Docker:

### 1. Configurar el entorno

```bash
cp .env.example .env
nano .env  # Agrega tu API key, profile ID y zona horaria
2. Configurar dominios
cp config.json.example config.json
nano config.json  # Configura tus dominios y horarios

3. Ejecutar con Docker Compose
docker compose up -d

Comandos de Docker
# Ver logs
docker compose logs -f

# Detener el contenedor
docker compose down

# Reconstruir después de cambios
docker compose up -d --build

# Verificar estado
docker compose ps

# Ejecutar una sincronización única
docker compose exec nextdns-blocker python nextdns_blocker.py sync -v

# Verificar estado de bloqueo
docker compose exec nextdns-blocker python nextdns_blocker.py status
Variables de entorno para Docker
| Variable             | Requerido | Predeterminado | Descripción                 |
| -------------------- | --------- | -------------- | --------------------------- |
| `NEXTDNS_API_KEY`    | Sí        | -              | Tu API key de NextDNS       |
| `NEXTDNS_PROFILE_ID` | Sí        | -              | Tu profile ID de NextDNS    |
| `TZ`                 | No        | `UTC`          | Zona horaria del contenedor |
Comandos
Comandos principales del bloqueador
# Sincronizar según los horarios (se ejecuta automáticamente cada 2 min)
nextdns-blocker sync

# Previsualizar lo que haría la sincronización sin aplicar cambios
nextdns-blocker sync --dry-run

# Sincronizar con salida detallada mostrando todas las acciones
nextdns-blocker sync --verbose
nextdns-blocker sync -v

# Verificar el estado actual del bloqueo
nextdns-blocker status

# Desbloquear manualmente un dominio (no funciona en dominios protegidos)
nextdns-blocker unblock example.com

# Pausar todo el bloqueo durante 30 minutos (predeterminado)
nextdns-blocker pause

# Pausar por una duración personalizada (por ejemplo, 60 minutos)
nextdns-blocker pause 60

# Reanudar el bloqueo inmediatamente
nextdns-blocker resume

# Buscar actualizaciones y actualizar
nextdns-blocker update

# Actualizar sin solicitud de confirmación
nextdns-blocker update -y
### Comandos de acciones pendientes

```bash
# Listar todas las acciones de desbloqueo pendientes
nextdns-blocker pending list

# Mostrar detalles de una acción pendiente específica
nextdns-blocker pending show <action-id>

# Cancelar una acción de desbloqueo pendiente
nextdns-blocker pending cancel <action-id>

# Cancelar sin solicitud de confirmación
nextdns-blocker pending cancel <action-id> -y
Comandos de configuración
bash
Copy code
# Mostrar la configuración actual
nextdns-blocker config show

# Editar la configuración en tu editor ($EDITOR)
nextdns-blocker config edit

# Establecer un valor de configuración
nextdns-blocker config set timezone America/New_York
nextdns-blocker config set editor vim

# Validar la sintaxis y estructura de la configuración
nextdns-blocker config validate

# Sincronizar dominios (igual que el sync principal, pero preferido)
nextdns-blocker config sync
Comandos del Watchdog
bash
Copy code
# Verificar el estado del cron
nextdns-blocker watchdog status

# Deshabilitar el watchdog por 30 minutos
nextdns-blocker watchdog disable 30

# Deshabilitar el watchdog permanentemente
nextdns-blocker watchdog disable

# Volver a habilitar el watchdog
nextdns-blocker watchdog enable

# Instalar manualmente los trabajos de cron
nextdns-blocker watchdog install

# Eliminar los trabajos de cron
nextdns-blocker watchdog uninstall

### Comandos del Modo Panico

Modo de bloqueo de emergencia que bloquea temporalmente todos los dominios y oculta comandos peligrosos.

```bash
# Activar modo panico por 1 hora
nextdns-blocker panic 60

# Verificar estado del modo panico
nextdns-blocker panic status

# Extender modo panico por 30 minutos
nextdns-blocker panic extend 30
```

Durante el modo panico:
- Todos los dominios se bloquean inmediatamente
- Comandos como `unblock`, `pause`, `resume`, `allow`, `disallow` estan ocultos
- La sincronizacion omite desbloqueos y operaciones de lista blanca
- Las acciones pendientes se pausan
- La duracion minima es de 15 minutos

Logs
bash
Copy code
# Ver logs de la aplicación
tail -f ~/.local/share/nextdns-blocker/logs/app.log

# Ver el log de auditoría (todas las acciones de bloqueo/desbloqueo)
cat ~/.local/share/nextdns-blocker/logs/audit.log

# Ver logs de ejecución de cron
tail -f ~/.local/share/nextdns-blocker/logs/cron.log

# Ver logs del watchdog
tail -f ~/.local/share/nextdns-blocker/logs/wd.log

# Ver trabajos de cron
crontab -l
Autocompletado de la shell
Habilita el autocompletado con tabulación para comandos, subcomandos y nombres de dominio.

Bash - agregar a ~/.bashrc:

bash
Copy code
eval "$(nextdns-blocker completion bash)"
Zsh - agregar a ~/.zshrc:

bash
Copy code
eval "$(nextdns-blocker completion zsh)"
Fish - guardar en el directorio de completions:

bash
Copy code
nextdns-blocker completion fish > ~/.config/fish/completions/nextdns-blocker.fish
 Después de agregar el script de autocompletado, reinicia tu shell o vuelve a cargar el archivo de configuración.
 **Qué se completa:**

| Contexto | Completaciones |
|---------|----------------|
| `nextdns-blocker <TAB>` | Todos los comandos |
| `nextdns-blocker config <TAB>` | Subcomandos: edit, show, sync, etc. |
| `nextdns-blocker unblock <TAB>` | Nombres de dominio de tu blocklist |
| `nextdns-blocker disallow <TAB>` | Nombres de dominio de tu allowlist |
| `nextdns-blocker pending cancel <TAB>` | IDs de acciones pendientes |
| `nextdns-blocker --<TAB>` | Flags: --help, --version, --no-color |

## Configuración

### Variables de entorno (.env)

| Variable | Requerido | Predeterminado | Descripción |
|----------|----------|---------|-------------|
| `NEXTDNS_API_KEY` | Sí | - | Tu API key de NextDNS |
| `NEXTDNS_PROFILE_ID` | Sí | - | Tu profile ID de NextDNS |
| `API_TIMEOUT` | No | `10` | Tiempo de espera de solicitudes a la API en segundos |
| `API_RETRIES` | No | `3` | Número de intentos de reintento |
| `DISCORD_WEBHOOK_URL` | No | - | URL del webhook de Discord para notificaciones |
| `DISCORD_NOTIFICATIONS_ENABLED` | No | `false` | Habilitar notificaciones de Discord (`true`/`false`) |

> **Nota:** La zona horaria ahora se configura en `config.json` bajo `settings.timezone` y se detecta automáticamente durante la configuración.

### Notificaciones de Discord

Recibe alertas en tiempo real cuando los dominios se bloquean o desbloquean:

1. Crea un webhook de Discord en tu servidor (Configuración del servidor → Integraciones → Webhooks)
2. Agrégalo a tu `.env`:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_NOTIFICATIONS_ENABLED=true
Las notificaciones muestran:

Nombre del dominio

Acción (bloqueado/desbloqueado)

Marca de tiempo

Embeds codificados por color (rojo=bloqueo, verde=desbloqueo)

Horarios de dominios

Edita config.json para configurar qué dominios administrar y sus horarios de disponibilidad:
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York",
    "editor": null
  },
  "blocklist": [
    {
      "domain": "reddit.com",
      "description": "Social media",
      "unblock_delay": "0",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "12:00", "end": "13:00"},
              {"start": "18:00", "end": "22:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "10:00", "end": "22:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "gambling-site.com",
      "description": "Always blocked",
      "unblock_delay": "never",
      "schedule": null
    }
  ],
  "allowlist": []
}

Opciones de configuración de dominio
| Campo           | Requerido | Descripción                                                  |
| --------------- | --------- | ------------------------------------------------------------ |
| `domain`        | Sí        | Nombre de dominio a administrar                              |
| `description`   | No        | Descripción legible para humanos                             |
| `unblock_delay` | No        | Tiempo de espera antes de ejecutar el desbloqueo (ver abajo) |
| `schedule`      | No        | Horario de disponibilidad (null = siempre bloqueado)         |

Opciones de retraso de desbloqueo
El campo unblock_delay crea fricción contra el desbloqueo impulsivo:
| Valor     | Comportamiento                                 |
| --------- | ---------------------------------------------- |
| `"0"`     | Desbloqueo instantáneo (sin protección)        |
| `"30m"`   | Desbloqueo en cola, se ejecuta en 30 minutos   |
| `"4h"`    | Desbloqueo en cola, se ejecuta en 4 horas      |
| `"24h"`   | Desbloqueo en cola, se ejecuta en 24 horas     |
| `"never"` | No se puede desbloquear (totalmente protegido) |
Cuando se establece un retraso, intentar desbloquear crea una acción pendiente:

$ nextdns-blocker unblock bumble.com

Unblock scheduled for 'bumble.com'
Delay: 24h
Execute at: 2025-12-16T03:45:00
ID: pnd_20251215_034500_a1b2c3

Use 'pending list' to view or 'pending cancel' to abort
Puedes cancelar la acción pendiente antes de que se ejecute:

$ nextdns-blocker pending cancel a1b2c3
Cancelled pending unblock for bumble.com


Esto se basa en investigaciones que muestran que los impulsos normalmente desaparecen en 20–30 minutos. El retraso crea espacio para tomar mejores decisiones.

Los cambios surten efecto en la siguiente sincronización (cada 2 minutos).

Consulta SCHEDULE_GUIDE.md
 para documentación completa y ejemplos.

Allowlist (Excepciones)

Usa la allowlist para mantener accesibles subdominios específicos incluso cuando su dominio principal está bloqueado. Las entradas de allowlist también admiten horarios para acceso basado en tiempo:
{
  "domains": [
    {
      "domain": "amazon.com",
      "description": "E-commerce - blocked with schedule",
      "schedule": { ... }
    }
  ],
  "allowlist": [
    {
      "domain": "aws.amazon.com",
      "description": "AWS Console - always accessible"
    },
    {
      "domain": "youtube.com",
      "description": "Streaming - blocked by NextDNS category, allow evenings",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
            "time_ranges": [{ "start": "20:00", "end": "22:30" }]
          }
        ]
      }
    }
  ]
}
Comportamiento de la allowlist
Horario	Comportamiento
null o ausente	Siempre en la allowlist (24/7)
definido	Solo en la allowlist durante las horas programadas

Allowlist programada es útil para dominios bloqueados por categorías o servicios de NextDNS

Fuera del horario programado, el dominio se elimina de la allowlist (la categoría/servicio lo bloquea)

Durante el horario programado, el dominio se agrega a la allowlist (desbloqueado)

Un dominio no puede estar en domains (denylist) y en allowlist al mismo tiempo

Útil para excepciones de subdominios: bloquear amazon.com pero permitir aws.amazon.com

Los cambios se sincronizan automáticamente cada 2 minutos
Comandos de allowlist
# Agregar dominio a la allowlist (siempre accesible)
nextdns-blocker allow aws.amazon.com

# Eliminar dominio de la allowlist
nextdns-blocker disallow aws.amazon.com

# Ver el estado actual incluyendo allowlist
nextdns-blocker status
Zona horaria

La zona horaria se detecta automáticamente durante init según la configuración de tu sistema:

macOS/Linux: Lee el enlace simbólico /etc/localtime

Windows: Usa el comando tzutil /g

Fallback: Variable de entorno TZ o UTC

La zona horaria se guarda en config.json bajo settings.timezone. Para cambiarla:

nextdns-blocker config set timezone America/New_York


Consulta la Zona horaria

La zona horaria se detecta automáticamente durante init según la configuración de tu sistema:

macOS/Linux: Lee el enlace simbólico /etc/localtime

Windows: Usa el comando tzutil /g

Fallback: Variable de entorno TZ o UTC

La zona horaria se guarda en config.json bajo settings.timezone. Para cambiarla:

nextdns-blocker config set timezone America/New_York


Consulta la lista de zonas horarias
## Solución de problemas

**¿La sincronización no funciona?**
- Verifica cron: `crontab -l` (deberías ver el trabajo de sync ejecutándose cada 2 minutos)
- Revisa los logs: `tail -f ~/.local/share/nextdns-blocker/logs/app.log`
- Prueba manualmente: `nextdns-blocker sync`
- Valida el JSON: `python3 -m json.tool config.json`

**¿Errores en config.json?**
- Asegúrate de que la sintaxis JSON sea válida (usa [jsonlint.com](https://jsonlint.com))
- Verifica que el formato de hora sea HH:MM (24 horas)
- Verifica que los nombres de los días estén en minúsculas (monday, tuesday, etc.)
- Los nombres de dominio deben ser válidos (sin espacios ni caracteres especiales)
- Valida con: `nextdns-blocker config validate`
- Consulta `config.json.example` como referencia

**¿Zona horaria incorrecta?**
- Cambia con: `nextdns-blocker config set timezone America/New_York`
- O vuelve a ejecutar `nextdns-blocker init` (la zona horaria se detecta automáticamente)
- Revisa los logs para verificar que la zona horaria se esté utilizando

**¿Timeouts de la API?**
- Incrementa `API_TIMEOUT` en `.env` (por defecto: 10 segundos)
- Incrementa `API_RETRIES` en `.env` (por defecto: 3 intentos)

**¿Cron no se está ejecutando?**
```bash
# Verificar el estado del servicio cron
sudo service cron status || sudo service crond status

# Verificar el estado del watchdog
nextdns-blocker watchdog status
Solución de problemas en Windows

¿El Programador de tareas no se está ejecutando?

# Verificar el estado del Programador de tareas
nextdns-blocker watchdog status

# Ver tareas en la interfaz gráfica del Programador de tareas
taskschd.msc

# Listar tareas desde la línea de comandos
schtasks /query /tn "NextDNS-Blocker-Sync"
schtasks /query /tn "NextDNS-Blocker-Watchdog"

# Ejecutar manualmente la tarea de sincronización
schtasks /run /tn "NextDNS-Blocker-Sync"


¿Rutas con espacios causan problemas?

La aplicación maneja automáticamente rutas con espacios

Si ves errores, verifica que tu nombre de usuario no contenga caracteres especiales como <, >, |, &

Los archivos de log se almacenan en: %LOCALAPPDATA%\nextdns-blocker\logs\

¿El script de PowerShell no se ejecuta?

# Verificar la política de ejecución
Get-ExecutionPolicy

# Permitir scripts para el usuario actual (si es necesario)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Ejecutar instalador
.\install.ps1


Ver logs en Windows

# Log de la aplicación
Get-Content "$env:LOCALAPPDATA\nextdns-blocker\logs\app.log" -Tail 50

# Log de sincronización
Get-Content "$env:LOCALAPPDATA\nextdns-blocker\logs\sync.log" -Tail 50

# Log de auditoría
Get-Content "$env:LOCALAPPDATA\nextdns-blocker\logs\audit.log" -Tail 50


Permisos de archivos en Windows

Windows utiliza ACLs en lugar de permisos Unix (0o600)

Los archivos se crean con permisos predeterminados del usuario

Los archivos de configuración en %APPDATA%\nextdns-blocker\ solo son accesibles por el usuario actual en configuraciones típicas

Desinstalación
# Eliminar trabajos de cron
nextdns-blocker watchdog uninstall

# Eliminar archivos
rm -rf ~/nextdns-blocker

# Eliminar logs (opcional)
rm -rf ~/.local/share/nextdns-blocker

Rotación de logs

Para evitar que los archivos de log crezcan indefinidamente, configura la rotación de logs:

chmod +x setup-logrotate.sh
./setup-logrotate.sh


Esto configura la rotación automática con:

app.log: diario, retención de 7 días

audit.log: semanal, retención de 12 semanas

cron.log: diario, retención de 7 días

wd.log: diario, retención de 7 días

Desarrollo
Ejecución de pruebas
pip install -e ".[dev]"
pytest tests/ -v

Cobertura de pruebas
pytest tests/ --cov=nextdns_blocker --cov-report=html


Cobertura actual: 94% con 1154 pruebas.

Calidad del código

La base de código sigue estas prácticas:

Type hints en todas las funciones

Docstrings con documentación de Args/Returns

Excepciones personalizadas para manejo de errores

Permisos de archivo seguros (0o600)

Validación de entradas antes de llamadas a la API

Documentación

SCHEDULE_GUIDE.md
 - Guía completa de configuración de horarios con ejemplos

examples/
 - Plantillas de configuración listas para usar:

minimal.json - Plantillas de inicio rápido

work-focus.json - Reglas enfocadas en productividad

gaming.json - Programación de plataformas de juegos

social-media.json - Gestión de redes sociales

parental-control.json - Bloqueo de contenido protegido

study-mode.json - Programación para estudiantes sin distracciones

config.json.example
 - Archivo de configuración de ejemplo

CONTRIBUTING.md
 - Guía de contribución

Seguridad

Nunca compartas tu archivo .env (contiene la API key)

.gitignore está configurado para ignorar archivos sensibles

Todas las solicitudes a la API usan HTTPS

Los archivos sensibles se crean con permisos 0o600

Los nombres de dominio se validan antes de las llamadas a la API

El log de auditoría registra todas las acciones de bloqueo/desbloqueo

Licencia

MIT

❓ Preguntas frecuentes
¿Cuál es la diferencia entre esta herramienta y el panel de NextDNS?

Mientras que el panel de NextDNS permite activar o desactivar manualmente listas de bloqueo o establecer controles parentales básicos, nextdns-blocker es un agente de automatización. Permite:

Programación dinámica: Bloquear y desbloquear dominios específicos automáticamente en horarios precisos (por ejemplo, bloquear sitios de juegos solo durante horas de estudio).

Aplicación del estado: La función "Watchdog" monitorea activamente tu configuración para asegurar que las restricciones no hayan sido deshabilitadas o eludidas manualmente.

¿Cómo obtengo mi API Key y Profile ID de NextDNS?

Profile ID: Es el código de 6 caracteres que se encuentra en la URL de tu panel de NextDNS (por ejemplo, https://my.nextdns.io/abcdef → abcdef).

API Key: Ve a tu página de cuenta de NextDNS
, desplázate hasta la sección "API Key" y haz clic para mostrar/copiar tu clave.

¿Esta herramienta bloquea anuncios automáticamente?

No. Esta herramienta está diseñada para gestionar políticas de acceso (bloquear sitios web/aplicaciones específicas) en lugar de mantener listas de bloqueo de anuncios. Para bloqueo de anuncios, habilita la NextDNS Ads & Trackers Blocklist directamente en la configuración de tu perfil.

¿Cómo funciona la función "Watchdog"?

El Watchdog se ejecuta en segundo plano para evitar cambios no autorizados. Si un dominio bloqueado se desbloquea manualmente desde el panel (o por otro usuario), el Watchdog detecta la discrepancia y vuelve a aplicar inmediatamente la regla de bloqueo para mantener la política de seguridad.

¿Dónde puedo ver qué cambios ha realizado el blocker?

La herramienta incluye una función de Log de auditoría. Revisa los archivos de log generados (la ubicación por defecto suele estar en el directorio de instalación) para ver el historial de todas las acciones de bloqueo/desbloqueo y eventos de aplicación del watchdog.

¿Puedo ejecutar esto en una Raspberry Pi?

Sí. Como nextdns-blocker es un paquete de Python, es liviano y compatible con cualquier sistema que soporte Python 3, incluyendo Raspberry Pi, servidores Linux, macOS y Windows.
