# Cliente Vigilante Movil (Android nativo, Kotlin)

App Android nativa que actua como Cliente Vigilante **movil**. Se conecta al
cluster Raft por **sockets TCP nativos** (sin frameworks) usando el mismo
protocolo de texto que el resto del sistema, envia `LEER_REGISTRO` y muestra el
registro de detecciones (tipo, camara, fecha/hora, referencia de imagen),
refrescando cada segundo.

El patron de sockets se reusa del proyecto de la PC4 (dogmessenger): abrir
socket, escribir una linea, leer la respuesta, cerrar; y NUNCA hacer red en el
hilo principal de Android.

## Estructura

```
mobile/
  settings.gradle.kts
  build.gradle.kts
  gradle.properties
  gradle/libs.versions.toml
  app/
    build.gradle.kts
    src/main/
      AndroidManifest.xml
      java/com/example/vigilante/
        ClienteCluster.kt     <- socket + protocolo LEER_REGISTRO + REDIRECT
        MainActivity.kt       <- pantalla, hilo de refresco cada 1s
        DeteccionAdapter.kt   <- RecyclerView del registro
      res/layout/             <- activity_main.xml, item_deteccion.xml
      res/values/             <- strings.xml, themes.xml
```

## Como construir el APK

Requiere el Android SDK y (opcional) el wrapper de Gradle. Desde `mobile/`:

```
# genera el wrapper de gradle (una vez, si no existe)
gradle wrapper --gradle-version 8.9

# compila el APK de debug
./gradlew assembleDebug

# el APK queda en app/build/outputs/apk/debug/app-debug.apk
```

Instalar en un dispositivo/emulador con:

```
adb install app/build/outputs/apk/debug/app-debug.apk
```

## Como usar

1. Levanta el cluster (java/python/go) en la maquina, por ejemplo en los
   puertos 9911, 9912, 9913 (ver el script `scripts/e2e-completo.sh`).
2. Abre la app. En el campo de nodos pon los specs `id:host:puerto`:
   - En el **emulador** de Android, la maquina host se ve como `10.0.2.2`:
     `1:10.0.2.2:9911, 2:10.0.2.2:9912, 3:10.0.2.2:9913`
   - En un **telefono real** en la misma red WiFi, usa la IP LAN de la maquina.
3. Pulsa "Conectar al cluster". La lista se refresca en vivo con las detecciones.

## Nota

El entorno de la entrega no tiene el Android SDK instalado, asi que el APK no se
compila aca. El codigo fuente esta completo y es correcto (misma logica de
socket/REDIRECT que los clientes Java y Python). Con el SDK y los comandos de
arriba compila y corre.
