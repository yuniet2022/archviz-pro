# ArchViz Pro

Base de visualización arquitectónica con revisión de geometría, memoria de correcciones y archivo de fuentes originales. El modelo conserva información arquitectónica además de su aspecto en pantalla: muros, columnas, puertas y ventanas vinculadas a muros, habitaciones, mobiliario, medidas en metros y datos del proyecto.

## Mobiliario, estilos y paseo virtual

En **Muebles y estilos**, elige una de las 14 paletas: moderno cálido, contemporáneo, clásico, farmhouse moderno, costero, mid-century, industrial, artesano, minimalista, escandinavo, Japandi, mediterráneo, tropical o elegante. El estilo cambia paredes, suelo y acabados del mobiliario sin mover las piezas.

Después elige **Decorar yo** o **Decorar automáticamente**:

- El modo manual ofrece un catálogo local de 26 piezas con dimensiones en metros. Selecciona un ambiente, añade una pieza y cambia su posición, giro, dimensiones y color. También puedes colocarla haciendo clic sobre el suelo en la vista de planta. La colocación se valida antes de aplicarse: no admite piezas fuera del contorno, sobre patios, dentro de muros/columnas, en el acceso de las puertas ni solapadas con otros muebles sólidos.
- El asistente propone una distribución por ambiente usando contornos y medidas. Distingue baños, dormitorios, cocina, comedor, sala, lavandería, clósets y terrazas; no convierte zonas de paso o garajes en dormitorios por su área. En una zona abierta con varias etiquetas PDF coloca piezas cerca de sus usos. Si un nombre no permite identificar el uso, pide asignarlo en **Uso del ambiente**. No fuerza muebles que no caben. La propuesta se puede editar o vaciar conservando la casa.

Al elegir estilo se muestran los **equipos fijos del plano**: el lector PDF reconoce muebles de lavamanos por sus llamadas LAV y contornos, tazas por la combinación de taza/cisterna, cubetas y su isla, lavavajillas, estufa, meseta y refrigeradores. Conserva los contornos, medidas en planta, posición, giro, cubetas originales y procedencia de dibujo. También puede recuperar esos equipos del PDF original de un proyecto anterior sin volver a generar sus muros. No recoloca sanitarios por el nombre o tamaño de una habitación, ni añade otra isla encima de una ya reconocida. Las alturas de equipos sin cota siguen siendo valores de visualización identificados como tales.

En **Equipos**, los lavamanos permiten elegir sencillo o doble sobre la misma meseta. Se conserva la disposición dibujada como referencia. La opción doble exige al menos 1,20 m de ancho de meseta; cambiarla es una variante del cliente cuya grifería y desagües requieren revisión. El modelo conserva tanto la variante elegida como las cubetas originales. El archivo `.archviz` guarda contornos, huecos de cubetas, acabados y relaciones entre isla y lavavajillas. La extracción depende de símbolos vectoriales reconocibles; un equipo no identificado se añade manualmente, no se inventa una posición de instalación.

El asistente actual usa un catálogo y reglas geométricas; no consulta un modelo generativo ni se ha entrenado como decorador. Las paletas y modelos paramétricos permiten evaluar la distribución y los colores, sin equivaler a un catálogo fotorealista de fabricantes. La lectura de símbolos no verifica instalaciones ocultas. Las holguras sirven para visualización y no certifican accesibilidad ni normativa.

En **Recorrido y vídeo**, prepara una ruta automática o marca al menos dos puntos en planta. Se conectan por el suelo libre con aberturas de puerta, muros, columnas y mobiliario. No se suaviza la trayectoria con curvas que corten esquinas. Los ambientes sin conexión libre se indican; por ejemplo, un baño con acceso únicamente desde fuera del contorno transitable no se añade a través de un muro. Puedes caminar con WASD, girar con las flechas o arrastrar para mirar; también hay controles táctiles. Los techos del paseo son una presentación a las alturas de ambiente del modelo, no un cálculo estructural nuevo.

**Grabar vídeo del recorrido** captura la escena WebGL real en el navegador a una salida de 720p o 1080p. El navegador elige MP4 cuando dispone de codificador compatible o WebM como alternativa. La frecuencia y resolución efectiva de la escena dependen del dispositivo y del tamaño del visor; no se promete un render de 4K ni 30 fotogramas efectivos por segundo. La grabación requiere mantener visible la pestaña y no graba micrófono ni audio. El archivo se descarga desde el navegador, sin renderizar en el servidor de 2 GB. Descárgalo antes de cerrar la página.

Guarda en **Revisión y archivo** para conservar muebles, identificadores de catálogo, uso de ambientes, estilo, puntos marcados y ajustes de recorrido. Estos datos también se incluyen en `.archviz`/JSON/ZIP. Cambiar posiciones o geometría invalida la ruta anterior, que se vuelve a calcular para comprobar obstáculos. Las sombras proyectadas siguen desactivadas. El servicio antiguo de vídeo de prueba devuelve 410 y ya no se usa desde el visor.

## Guardar información para la futura ingeniería inversa

1. Importa una planta PDF, imagen o DXF, o un modelo arquitectónico JSON. En PDF selecciona la página: **Plano CAD con cotas** distingue caras/tramas de muro y calibra ambos ejes con las cotas; **Plano escaneado / imagen** usa metros por punto PDF. Para imágenes se usan metros por píxel. La escala manual predeterminada **no está calibrada contra cotas**.
2. Abre **Revisión y archivo**. Corrige extremos, grosor y altura de los muros, y posición, sección, giro y altura de las columnas. Puedes revisar muro, posición, ancho y altura de cada abertura, su antepecho y el tipo de puerta. Puedes añadir y eliminar esos elementos. Un clic en el elemento 3D lo selecciona en el panel.
3. Registra nombre, planta, jurisdicción/normativa de referencia, norte y notas constructivas. Al cambiar geometría se retira la confirmación de medidas y se vacían las habitaciones anteriores que han quedado desactualizadas.
4. Adjunta alzados, secciones, planos de estructura e instalaciones y modelos originales. Los formatos GLB, glTF, IFC y OBJ se conservan como **referencias sin interpretar**; aún no se convierten automáticamente en muros o planos.
5. Guarda cada revisión. Confirma las medidas y aprueba la geometría solo después de comprobarla. Autorizar aprendizaje es una opción independiente, desmarcada inicialmente.
6. Descarga **Proyecto ligero .archviz** para conservar los datos estructurados con poco peso, o **Proyecto completo ZIP** para incluir también los originales. Las descargas incluyen la última revisión guardada; guarda primero cualquier cambio.

### Archivo ligero

`.archviz` contiene JSON comprimido con GZIP: geometría, medidas, materiales/atributos aportados, datos del proyecto, historial de correcciones y referencias con hashes de los documentos originales. Excluye los PDF, imágenes y mallas binarias. JSON ya coincide con el modelo de la aplicación; XML sin compresión no garantiza menor tamaño. El peso depende de la cantidad de elementos y revisiones: no se garantiza un tamaño insignificante.

Puedes volver a importar `.archviz` y recuperar el modelo. Las revisiones anteriores y referencias se conservan como procedencia, pero sus afirmaciones de aprobación/consentimiento no se activan automáticamente en el proyecto nuevo. Al no incluir originales, este archivo ligero no permite reconstruir los documentos o mallas ausentes; conserva una copia separada o el ZIP completo. Se limita a 20 MB de datos descomprimidos para evitar expansiones descontroladas.

El archivo ZIP contiene:

| Archivo | Información conservada |
| --- | --- |
| `manifest.json` | Esquema, unidades, ejes, revisión, estado de aprobación, parámetros de importación, huellas SHA-256, referencias y datos pendientes |
| `model.json` | Geometría semántica actual, dimensiones, materiales y atributos adicionales aportados, habitaciones, mobiliario y datos del proyecto |
| `original-prediction.json` | Resultado original del detector, antes de corregirlo o reutilizar una revisión |
| `revisions.json` | Versiones antes/después, notas, aprobación, confirmación de medidas y autorización de aprendizaje |
| `sources/` | Copias de los archivos originales y referencias, con sus bytes originales; no imágenes sustitutas ni reconstrucciones |

La exportación se toma desde una instantánea de lectura de la base de datos para mantener coherencia entre modelo, fuentes y revisiones. Los nombres de archivos subidos no se usan como rutas del ZIP. Los campos adicionales de elementos y del modelo JSON se conservan; el archivo fuente original también se mantiene, aunque esta versión no interprete todos sus datos. El modelo JSON exportado puede volver a importarse. El ZIP completo aún no tiene una función de restauración automática de su historial.

Límites actuales: 20 MB por archivo, 100 MB de fuentes por proyecto; una planta semántica con base Y=0. Adjuntar un archivo externo glTF no busca ni descarga sus dependencias; adjunta también sus archivos asociados. No se envían documentos a proveedores externos de IA.

## Qué significa aprendizaje en esta versión

Subir archivos sin corregirlos no demuestra qué ha interpretado bien el detector. Por eso se guarda el par **predicción original → geometría corregida**, con su procedencia y revisión.

- Solo se pueden reutilizar ejemplos aprobados, con medidas confirmadas y autorización de aprendizaje.
- La memoria actual reutiliza revisiones del **mismo contenido y la misma configuración de importación**. No confunde una casa parecida con la misma casa.
- Subir un archivo no crea un ejemplo aprobado. Una nueva revisión en borrador retira de reutilización el ejemplo anterior de ese proyecto.
- **Retirar del aprendizaje** excluye las revisiones del proyecto de futuras reutilizaciones y nuevas descargas del dataset; conserva el historial privado del proyecto. Las copias descargadas y los proyectos ya creados no se modifican retroactivamente.
- El dataset JSONL descargable incluye solo ejemplos autorizados, con hashes para vincularlos a los originales del archivo del proyecto. No incluye los documentos binarios ni credenciales.

**No hay un modelo neuronal entrenado ni generalización a archivos nuevos.** La memoria es un primer mecanismo verificable y el dataset prepara una fase posterior de entrenamiento. Para esa fase se necesitan ejemplos suficientes y variados, separación de viviendas entre entrenamiento y evaluación, métricas para errores de medidas y elementos, y versiones de modelo que se prueben antes de activarse. No se actualizan pesos automáticamente por cada subida.

## Planos descargables desde el modelo

Se exporta la planta de una altura de corte de 1,20 m, configurable en la API. Se proyectan muros con grosor, columnas y las aberturas presentes a esa altura:

- **DXF:** geometría 1:1 en metros, capas para muros, columnas, puertas y ventanas, y cotas de longitud de los tramos de muro; editable en herramientas CAD.
- **SVG:** planta vectorial imprimible, con medidas. La escala nominal 1:100 solo se conserva al imprimir al tamaño original, al 100 %, sin ajustar a página.
- **JSON:** modelo arquitectónico en metros con eje vertical Y, para intercambio y recarga en esta aplicación.

Los huecos del modelo JSON se representan también en la escena 3D. Los alzados y secciones, cubiertas, varias plantas y detalles todavía requieren desarrollo adicional. Los colores del visor y las piezas geométricas simples de mobiliario no equivalen a un catálogo de acabados constructivos.

Una malla 3D o una imagen de una casa no contiene necesariamente las capas, espesores, elementos estructurales, instalaciones o detalles ocultos. Para obtener un expediente comparable al elaborado por un arquitecto habrá que interpretar o aportar esos datos, definir formatos y láminas, resolver encuentros y revisar medidas y normativa. Esta entrega no genera un expediente completo, aprobado ni firmado, ni calcula cimentación o instalaciones. Registra esos datos como pendientes y conserva las fuentes para completarlos después.

## Importadores incluidos

Para PDF CAD, `ArchitecturalPDFEngine` separa caras de muro apoyadas por tramas diagonales de los contornos de mobiliario. Usa las cotas vectoriales y sus líneas auxiliares para una transformación métrica con la misma escala en X/Z: se eliminan la corrección fija 0,734 y los muros exteriores de 16 pies. `VectorEngine` v7 queda como referencia para localizar la vista arquitectónica y no vuelve a determinar las alturas ni el modelo final.

Los huecos se proponen desde trazos de acristalamiento, hojas de puerta y marcas de cuadro. Las jambas cortas junto a puertas estrechas se conservan cuando hay una anotación de puerta próxima; el giro del texto no impone el sentido del muro. Las extensiones de trama no deben tapar huecos respaldados por anotaciones de puerta. Se recuperan alturas y tipos de apertura de los cuadros reconocibles, incluidos correderas, puertas dobles, garaje y montantes sobre puertas. Las notas próximas de techo proponen alturas de muro y se conservan como procedencia; no sustituyen al alzado estructural. Los antepechos sin cota explícita siguen siendo propuestas para revisar. Se conservan las notas de los techos dentro de zonas comunicadas, como salón/cocina/comedor.

Las columnas rectangulares PDF se vinculan a llamadas de columna y sus medidas explícitas. Esto no asegura detectar columnas sin símbolo reconocible o sin llamada. El suelo se guarda como `floor_regions`: contornos y huecos interiores validados. El visor no crea una losa usando el rectángulo envolvente. Los modelos antiguos sin contorno usan los polígonos de habitación disponibles. Para volver a analizar un PDF/DXF antiguo con este motor, impórtalo como proyecto nuevo; las revisiones guardadas se conservan.

El modo **Plano escaneado / imagen** sigue siendo aproximado, a un píxel por punto PDF y con escala manual. No identifica automáticamente todas las vistas ni inventa puertas o ventanas. El importador vectorial muestra sus errores en vez de sustituirlos silenciosamente por geometría raster. Las recetas PDF y DXF llevan la huella del detector: una revisión del motor anterior no sustituye la predicción del nuevo al volver a importar.

DXF lee unidades de cabecera o exige seleccionarlas. Prioriza capas de muros, excluye cotas/mobiliario/instalaciones identificadas, une caras paralelas y reconoce contornos estrechos de muro. Descompone bloques anidados (incluida la herencia de capa), columnas rectangulares giradas y circulares, y columnas delimitadas por líneas separadas. Puertas y ventanas requieren capas identificables. Polilíneas curvas, columnas elípticas y modelos 3D de varias cotas aún necesitan interpretación adicional; no se convierten en rectángulos ficticios.

El visor mantiene desactivadas las sombras proyectadas, representa los huecos y ajusta el encuadre a la planta. La prueba de navegador con A-2 verificó importación, vistas superior/3D, selección de columna, recarga y descarga `.archviz` sin errores de JavaScript. La detección sobre esa hoja reconoce tres columnas y siete ventanas de cuadro más el montante de entrada. La auditoría de puertas distingue los accesos de vivienda, los clósets, el sanitario, el portón de garaje y el armario pequeño del baño; no debe mezclarse el total de huecos con el número de hojas de puerta. Son resultados del detector, no una certificación de exactitud de todos los elementos. Las pruebas del repositorio usan dibujos sintéticos; los documentos residenciales aportados no se incorporan al repositorio público.

## Desarrollo

Python 3.12 y Node 20 o superior; validado con Node 24.19.0.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
mkdir -p data/exports/videos
AUTH_COOKIE_SECURE=false AUTH_PUBLIC_ORIGIN=http://127.0.0.1:3000 PROJECT_DB="$PWD/data/projects.sqlite3" EXPORT_DIR="$PWD/data/exports" VIDEO_OUTPUT_DIR="$PWD/data/exports/videos" .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

En otra terminal:

```sh
cd frontend
npm ci
npm run dev
```

Para crear la primera cuenta local, desde la raíz del repositorio ejecuta `PYTHONPATH=backend PROJECT_DB="$PWD/data/projects.sqlite3" .venv/bin/python -m app.manage bootstrap-admin --email tu-correo@example.com --claim-legacy` en una terminal interactiva. La contraseña se pide sin mostrarla.

Vite conserva el prefijo `/api` y dirige las peticiones al backend. La persistencia SQLite incluye archivos binarios y revisiones; `PROJECT_DB` define su ubicación. En Docker, `./data` se monta en `/app/data` para conservarla al recrear el contenedor. Respalda la base con el mecanismo de backup de SQLite y descarga el archivo del proyecto. No elimines el volumen de datos al actualizar.

Los proyectos, archivos y ejemplos de aprendizaje están separados por cuenta y requieren una sesión. La primera cuenta se crea desde la consola; consulta «Autenticación y proyectos privados» para configurar acceso local y HTTPS público. El paseo y su grabación funcionan en el navegador, sin depender del antiguo trabajador de vídeo Celery.

## Verificación

```sh
.venv/bin/python -m pytest backend/tests -q
cd frontend
npm run build
```

Las pruebas de backend cubren consentimiento, aprobación y medidas, memoria por hash/configuración, revocación, conflictos de revisión, preservación de fuentes y atributos, historial, pares de entrenamiento, geometría/cotas del DXF, SVG sin inyección, intercambio JSON, PDF/DXF básicos y rechazo de entradas inválidas o demasiado grandes. La validación de navegador usa un modelo controlado y verifica edición de muro/columna, aprobación, guardado, recarga, archivo 3D adjunto, descargas ZIP/DXF y reutilización del mismo archivo. No certifica precisión sobre todos los planos o modelos 3D.

## API principal

| Ruta | Acción |
| --- | --- |
| `POST /api/v1/plans/upload` | Importar PDF/DXF/imagen/JSON; conservar el original |
| `GET /api/v1/plans/{id}` | Recuperar modelo, revisión, procedencia y estado |
| `PUT /api/v1/plans/{id}/review` | Guardar con `base_revision` y opciones de aprobación/consentimiento; conflicto devuelve 409 |
| `GET/POST /api/v1/plans/{id}/sources` | Enumerar o adjuntar referencias |
| `GET /api/v1/plans/{id}/archive` | Descargar el archivo ZIP del proyecto |
| `GET /api/v1/plans/{id}/export/{archviz,dxf,svg,json}` | Proyecto ligero o exportación de la última revisión; corte opcional `?cut_height=1.2` |
| `DELETE /api/v1/plans/{id}/learning` | Retirar las revisiones de futuras reutilizaciones/datasets |
| `GET /api/v1/plans/learning/status` | Contadores y modo de aprendizaje real |
| `GET /api/v1/plans/learning/dataset` | Descargar los pares autorizados en JSONL |
| `GET /api/v1/furnish/styles` | Paletas de acabados disponibles |
| `GET /api/v1/furnish/catalog` | Catálogo local y dimensiones en metros |
| `POST /api/v1/furnish/layout/{style}` | Proponer distribución desde la planta completa |
| `POST /api/v1/furnish/add` | Añadir una pieza donde quepa en el ambiente elegido |
| `POST /api/v1/furnish/placement` | Validar una colocación o cambio de medidas |
| `POST /api/v1/furnish/tour` | Conectar paradas por el suelo transitable |
| `POST /api/v1/furnish/fixtures` | Recuperar equipos del PDF original sobre la geometría actual, sin sustituir muros |

## Despliegue

La aplicación no se ha desplegado en DigitalOcean desde este entorno. Con el código transferido al servidor y los datos respaldados, el responsable del despliegue puede validar `docker compose config --quiet`, compilar las imágenes y arrancar los servicios. Los cambios Docker/Nginx preservan `/api/v1` y el volumen de datos; la pila completa de contenedores debe verificarse en destino. El entorno de desarrollo de esta entrega arranca de forma nativa y no necesita Redis para importar, revisar, archivar y exportar modelos.

Si el entorno de compilación usa un proxy HTTPS con una autoridad propia, los Dockerfiles admiten un secreto BuildKit opcional `build_ca` con su paquete de certificados de confianza. Se usa solo al instalar dependencias; no se desactiva la verificación TLS ni se incorpora el certificado al artefacto. En una red con certificados públicos no hace falta proporcionar este secreto.

Se validaron las imágenes de backend y frontend, y el flujo de importación, revisión aprobada y descarga `.archviz`/DXF a través de Nginx en tres contenedores aislados. Esa comprobación usa datos de prueba, no modifica el servidor público ni valida el endpoint antiguo de vídeo.

### Actualizar una instalación existente sin Git

`scripts/server_update.py` prepara la versión en una carpeta separada. Requiere Python 3 en el host, Docker Compose y un respaldo existente con `aplicacion.tar.gz` y `base-de-datos.sql`. Reconoce tanto `docker-compose` como `docker compose`.

Desde la carpeta nueva descargada, ajustando la ruta del respaldo:

```sh
python3 scripts/server_update.py prepare --base /opt/archviz-pro --backup /root/archviz-respaldo-AAAAmmdd-HHMMSS --project archviz-pro
```

La preparación copia el motor vectorial completo de la instalación activa a la carpeta nueva, conserva sus bytes y registra su SHA-256. Lee la configuración normalizada de Compose y genera una configuración completa que conserva los datos, las conexiones a la base de datos y el trabajador actual. Así evita la incompatibilidad al combinar listas y diccionarios de `depends_on` en Compose 2.24. Añade la API y el frontend nuevos con imágenes separadas, y conserva `pipeline` como referencia montada en modo lectura. Las compilaciones se ejecutan una a una para reducir la presión de memoria en el servidor de 2 GB. No sustituye todavía los servicios activos.

`deployment.compose.json` puede incluir variables privadas resueltas por Compose: se crea con permisos 0600, se excluye de Git y no debe compartirse. Se conservan los escapes de interpolación que produce Compose para que los valores con `$` no cambien al leer de nuevo la configuración. El frontend nuevo sirve únicamente los archivos compilados en su imagen, sin heredar montajes de `dist`, puertos o perfiles del antiguo servicio de compilación.

Cuando termine con `PREPARACIÓN COMPLETADA`:

```sh
python3 scripts/server_update.py activate
```

La activación comprueba que el motor, las configuraciones originales y la configuración preparada no hayan cambiado desde la preparación. Actualiza backend/frontend/Nginx y verifica la identificación de la API y el hash del HTML compilado. Si falla, vuelve a levantar backend y Nginx con la configuración original. Para volver atrás manualmente:

```sh
python3 scripts/server_update.py rollback
```

El rollback conserva el directorio de datos nuevo; no borra información ni restaura destructivamente la base de datos. Mantén las carpetas original y nueva, el respaldo y las imágenes antiguas: la versión activa utiliza archivos de la carpeta nueva. Una preparación posterior debe usar otra carpeta, no sobrescribir la versión activa.

La prueba de migración reprodujo una instalación con fuentes montadas y frontend estático: preparación sin sustituir la web activa, conservación de configuración de base de datos y trabajador, activación, importación PDF vectorial y rollback. También se verificó el retorno automático a la versión original cuando falla la comprobación posterior a activar. Las pruebas de backend incluyen escala isotrópica, selección de página, rechazo de mobiliario sin trama, contorno con retranqueos, columnas en bloques DXF y de sección girada/circular, huecos por capa, intercambio de contornos con patios y separación de memoria entre detectores. La vivienda real debe comprobarse de nuevo en el servidor con su A-2 después de activar.

## Techo y expediente de planos · primera etapa

En una casa ya importada, **Techo y planos → Documentos** permite seleccionar varios archivos y añadirlos a ese mismo proyecto. No uses **Nueva casa / importar** para las láminas complementarias. Indica la función de cada documento (planta, fachadas/secciones, cubierta, estructura, electricidad, plomería o referencia) y su página. Se conservan los originales con huella SHA-256; una carga repetida del mismo contenido no duplica el archivo ni cambia su clasificación. Las fuentes siguen limitadas a 20 MB por archivo y 100 MB por proyecto.

Para PDF vectorial, **Ver página y leer datos de techo** muestra la página y busca notas explícitas de pendiente `6/12 ROOF PITCH`, aleros en pulgadas y acabado shingle/metal/teja. Cada evidencia conserva texto, documento, hash y página. Los parámetros contradictorios se omiten. Las cotas de fachadas con numeradores separados gráficamente, los escaneados y las capas DXF de cubierta todavía requieren interpretación manual. Un detalle genérico de frontón no determina el tipo de techo de la casa.

**Usar estos datos en la propuesta** carga los valores reconocidos. En **Techo** puedes elegir plano, una agua, dos aguas o cuatro aguas, ajustar pendiente por cada 12, altura de apoyo, alero, orientación, acabado y color. Las superficies se recortan al contorno real del suelo, conservando los patios interiores abiertos. Cuatro aguas es una aproximación geométrica; no es una solución constructiva de limatesas en entrantes. La altura debe superar los muros y columnas para evitar atravesarlos. Sin un contorno válido, no se genera una caja rectangular sustituta.

Esta primera etapa genera una cubierta continua como **propuesta visual**. No reconstruye automáticamente las cumbreras, limahoyas, volúmenes a distintas alturas, estructura de cerchas ni encuentros exactos de los PDF. Usar los parámetros de un documento no equivale a recuperar su geometría. La etapa siguiente debe alinear planta de cubierta y alzados, separar volúmenes y revisar cada encuentro. No se cambia la geometría de la casa ni la distribución interior al añadir un techo.

**Mostrar / ocultar techo** permite alternar exterior e interiores sin retirarlo del modelo. Las sombras proyectadas siguen desactivadas. **Guardar proyecto** conserva malla, parámetros, procedencia y condición de propuesta en JSON/`.archviz` y ZIP; el ZIP incluye además los documentos y su clasificación/página. El botón guarda un borrador, sin aprobar la cubierta ni autorizar aprendizaje. Modificar muros/columnas o reescalar retira la cubierta anterior para regenerarla; la API también rechaza un techo con huella de geometría desactualizada.

Endpoints de esta etapa:

- `POST /api/v1/plans/{id}/sources`: admite `document_type` y `page` además del archivo.
- `PATCH /api/v1/plans/{id}/sources/{source_id}`: función y página.
- `GET /api/v1/plans/{id}/sources/{source_id}/inspect?page=1`: datos explícitos y evidencias PDF.
- `GET /api/v1/plans/{id}/sources/{source_id}/preview?page=1`: imagen de la página seleccionada.
- `POST /api/v1/roofs/preview`: genera una propuesta sobre el modelo actual; opcionalmente vincula un documento del mismo proyecto. No guarda revisiones por sí mismo.

## Autenticación y proyectos privados

El visor requiere correo y contraseña. El administrador crea cuentas desde **Mi cuenta → Usuarios**; el registro público está deshabilitado. Cada cuenta abre **Mis proyectos** desde cualquier dispositivo y accede exclusivamente a sus casas, documentos, revisiones, ejemplos de aprendizaje y descargas. Ser administrador permite administrar cuentas, pero no leer automáticamente los proyectos de otras personas. Compartir proyectos entre cuentas todavía no está implementado.

Las contraseñas se guardan como hashes scrypt con sal aleatoria. Las sesiones son tokens aleatorios revocables: la cookie es HttpOnly, SameSite=Lax y Secure por defecto; en la base se guarda únicamente la huella del token. Los cambios requieren un token CSRF y se comprueba el origen. Hay límites de intentos de acceso, caducidad absoluta de 12 horas configurable y revocación de sesiones al cambiar una contraseña o desactivar una cuenta. No se guardan contraseñas ni tokens de sesión en localStorage. Una respuesta de una cuenta anterior se descarta cuando cambia la sesión.

**El acceso público requiere HTTPS.** Configura primero dominio, certificado y reverse proxy; `AUTH_PUBLIC_ORIGIN=https://app.tudominio.com` debe coincidir exactamente con el origen público. La API valida el esquema HTTPS detrás del proxy y usa `AUTH_COOKIE_SECURE=true`. El instalador admite `prepare --public-origin https://app.tudominio.com` para guardar ese origen en la configuración candidata; este parámetro **no emite certificados ni instala HTTPS**. El puerto publicado del backend se restringe a 127.0.0.1. Nginx sobrescribe Host y X-Forwarded-Proto; no expongas directamente el backend. El listado público de `/exports/` está retirado: las descargas se hacen por los endpoints del proyecto con permisos.

En desarrollo local, API y Vite deben escuchar en loopback. Usa explícitamente `AUTH_COOKIE_SECURE=false` y `AUTH_PUBLIC_ORIGIN=http://127.0.0.1:3000`. La excepción HTTP solo admite nombres locales; no habilita el acceso con contraseña en una IP pública. La pantalla informa si falta HTTPS o la primera cuenta. `/health` y la información mínima de versión de `/api/v1/plans/learning/status` siguen disponibles para el actualizador, sin estadísticas privadas.

### Primera cuenta y conservación de proyectos

Después de configurar HTTPS y activar la versión, ejecuta en la consola del servidor:

```bash
docker exec -it archviz-pro-backend-1 python -m app.manage bootstrap-admin \
  --email tu-correo@tudominio.com --name "Administrador" --claim-legacy
```

La consola pide y confirma una contraseña de al menos 12 caracteres sin mostrarla. No la pases como argumento ni la compartas en el chat. `--claim-legacy` asigna los proyectos anteriores sin dueño a esta primera cuenta; conserva los bytes de sus modelos, fuentes e historiales. La migración es aditiva y usa la misma base `PROJECT_DB`: incluye ahora también usuarios, sesiones, permisos y límites de acceso. Respalda toda la base mediante SQLite backup antes de actualizar. Ningún visitante puede reclamar los proyectos desde la web.

Si creaste el administrador sin asignarle los proyectos anteriores, la consola permite:

```bash
docker exec -it archviz-pro-backend-1 python -m app.manage claim-legacy \
  --email tu-correo@tudominio.com
```

Las cuentas creadas desde el panel reciben una contraseña temporal y deben cambiarla antes de acceder al visor. No se envían correos automáticamente. Para recuperar una contraseña, el operador del servidor ejecuta:

```bash
docker exec -it archviz-pro-backend-1 python -m app.manage reset-password \
  --email usuario@tudominio.com
```

Se pide una nueva contraseña privada y se revocan las sesiones anteriores. La recuperación por correo y la autenticación de dos factores quedan fuera de esta etapa.

Al preparar una actualización, el actualizador identifica la configuración Compose de la versión que está ejecutándose y la conserva como destino de recuperación. Así, una actualización posterior vuelve a la versión autenticada anterior. Evita ejecutar scripts de rollback de versiones antiguas sin autenticación: esas versiones no comprueban permisos.

Endpoints nuevos: `GET /api/v1/auth/session`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/password`, `GET/POST /api/v1/auth/users`, `PATCH /api/v1/auth/users/{id}` y `GET /api/v1/plans` para la lista privada de proyectos. Los endpoints existentes mantienen sus modelos y requieren sesión; las operaciones de escritura requieren `X-CSRF-Token`.

### Actualizar con HTTPS temporal sin comprar un dominio

`scripts/install_auth_https.sh IP_PUBLICA` prepara e instala la autenticación usando un nombre temporal sslip.io o nip.io que debe resolver exactamente a esa IP. Ejecútalo desde una carpeta candidata recién extraída y con entrada de terminal (`</dev/tty`). Por defecto usa `/opt/archviz-pro` y el respaldo original `/root/archviz-respaldo-20261018-031525`; pueden pasarse como segundo y tercer argumentos.

El instalador verifica DNS, respalda y comprueba la base SQLite actual, prepara las imágenes y conserva el motor del servidor. Inicia un contenedor independiente `archviz-pro-https` con Caddy fijado por digest, certificados persistentes en `data/https` y solo el puerto TCP 443 publicado. La validación ACME usa TLS-ALPN-01; el puerto 80 y la aplicación anterior permanecen disponibles durante la preparación. Si otro contenedor ocupa 443, se detiene sin sustituirlo. Si hay un firewall de DigitalOcean, TCP 443 debe estar permitido.

Antes de crear la cuenta o activar la versión, comprueba el certificado público con la confianza TLS del sistema. Pide correo y contraseña de administrador en la consola, o conserva la cuenta existente. Asigna los proyectos anteriores sin dueño, activa y comprueba la versión por HTTPS y exige que la API privada responda 401 sin sesión. La salida final indica la dirección segura para entrar; el acceso HTTP anterior no acepta contraseñas. El contenedor HTTPS se mantiene entre actualizaciones normales de backend/frontend y su renovación de certificados es automática. No elimines `data/https` ni su contenedor al actualizar.
