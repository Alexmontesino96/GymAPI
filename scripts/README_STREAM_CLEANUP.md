# Scripts de limpieza para Stream.io

Este directorio contiene scripts para gestionar y limpiar canales en Stream.io.

## delete_all_stream_chats_improved.py

Script principal para eliminar todos los canales de chat en Stream.io.

### Uso

```bash
# Modo simulación (dry-run) - solo muestra los canales que se eliminarían sin hacer cambios
python scripts/delete_all_stream_chats_improved.py --dry-run

# Eliminar todos los canales (solicita confirmación)
python scripts/delete_all_stream_chats_improved.py

# Eliminar todos los canales sin solicitar confirmación
python scripts/delete_all_stream_chats_improved.py --force

# Eliminar con menos mensajes de log
python scripts/delete_all_stream_chats_improved.py --quiet

# Ajustar tamaño de lote para mejor rendimiento
python scripts/delete_all_stream_chats_improved.py --batch-size 50
```

### Parámetros

- `--dry-run`: Ejecuta el script en modo simulación sin eliminar nada
- `--force`: Elimina sin solicitar confirmación
- `--quiet`: Reduce la cantidad de mensajes de log
- `--batch-size`: Número de canales a procesar por lote (predeterminado: 10)

## delete_channel.py

Script para eliminar un canal específico de Stream.io por su ID.

### Uso

```bash
# Eliminar un canal por su CID completo
python scripts/delete_channel.py --cid "messaging:nombre_canal"

# Eliminar un canal especificando tipo e ID por separado
python scripts/delete_channel.py --channel-type "messaging" --channel-id "nombre_canal"
```

### Parámetros

- `--cid`: CID completo del canal en formato "tipo:id"
- `--channel-type`: Tipo del canal (por ejemplo: "messaging")
- `--channel-id`: ID del canal

## Consideraciones

- La eliminación de canales es **permanente** y no se puede deshacer
- Los canales eliminados también pierden todos sus mensajes
- Se recomienda hacer un respaldo o un dry-run antes de eliminar canales en producción
- Estos scripts requieren que las variables de entorno de Stream estén configuradas correctamente 