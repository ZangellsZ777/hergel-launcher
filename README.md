# Hergel Launcher 0.20.1

Launcher de Hergel Studio para los eventos de Hergel Community. Descarga El Hormiguero desde GitHub: Minecraft Java 1.20.1, Forge 47.4.10 y el paquete aprobado de 34 mods.

La cuenta Microsoft, el nombre y la skin del jugador se cargan al iniciar sesión. En Windows la sesión se guarda cifrada para el usuario actual. Los ajustes permiten elegir la RAM y consultar actualizaciones. El launcher instala Java y los archivos del juego; FancyMenu ofrece el acceso al servidor.

## Actualizaciones

El repositorio configurado es `Zangells7777/hergel-launcher`. El aviso consulta `launcher-update.json` de la última release pública. El catálogo del evento consulta `catalog.json` en esa misma release; si no hay conexión utiliza el catálogo incluido. Los instaladores y paquetes se verifican mediante SHA-256 antes de usarse. El instalador no incluye el ZIP del modpack. Al pulsar Descargar se recupera de GitHub, se verifica y se instala; las descargas verificadas se reutilizan. La primera instalación del evento necesita conexión.

## Preparación inicial de GitHub

1. Subir este proyecto a la raíz del repositorio. `packs/hormiguero.zip` está excluido de Git: se distribuye como archivo de release.
2. Crear una release **prerelease** con etiqueta `event-assets-v1` y adjuntar `Hormiguero-Paquete-Jugadores.zip`. No marcarla como Latest: la última release estable se reserva para el launcher.
3. En Actions ejecutar **Compilar Hergel Launcher**, inicialmente con `publicar` desactivado. El proceso recupera el paquete para verificarlo y ejecutar las pruebas; compila el launcher excluyendo el ZIP del modpack y comprueba su apertura en Windows antes de crear el instalador.
4. Descargar el artefacto de prueba y verificar el inicio de sesión, la descarga, el juego y la conexión al servidor en Windows.
5. Ejecutar de nuevo el flujo con `publicar` activado para crear la release `v0.20.1` con el instalador y ambos anuncios. Si esa versión ya existe, incrementar `hergel/version.py` antes de publicar.

El instalador de los jugadores es `Hergel-Launcher-Instalador.exe`; no necesitan Python. Los artefactos de Actions sirven para pruebas; la descarga pública sale de Releases.

Las versiones anteriores cuyo `launcher_updates.json` estaba vacío necesitan instalar esta primera versión configurada para recibir los avisos futuros.

## Versiones siguientes

Cambiar `hergel/version.py`, enviar los cambios y ejecutar el mismo flujo. `minima=0.0.0` permite posponer la actualización. Una versión mínima superior a la instalada obliga a actualizar antes de jugar. Publicar solo versiones superiores a la última distribuida.

Para cambiar el modpack: crear un ZIP limpio, generar su manifiesto `packs/hormiguero.json`, alojarlo bajo una etiqueta nueva y actualizar `pack-source.json` con URL, tamaño y SHA-256. El catálogo publicado debe corresponder exactamente al paquete verificado. Mantener los paquetes anteriores disponibles.

## Desarrollo local

Extraer el paquete completo, instalar `requirements.txt` y ejecutar `py run.py` o `ABRIR-HERGEL.bat`. En una copia recuperada de Git, ejecutar antes `py tools/descargar_paquete.py`. Compilación local de Windows: `CREAR-INSTALADOR.bat`, con Inno Setup 6 instalado.

Pruebas: `py -m unittest discover -s tests -v`. La comprobación gráfica del ejecutable se ejecuta en el flujo de Windows y no contacta los servicios Microsoft ni Minecraft.
