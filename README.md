# ArchViz Pro

Base de visualización arquitectónica con revisión de geometría, memoria de correcciones y archivo de fuentes originales. El modelo conserva información arquitectónica además de su aspecto en pantalla: muros, columnas, puertas y ventanas vinculadas a muros, habitaciones, mobiliario, medidas en metros y datos del proyecto.

## Guardar información para la futura ingeniería inversa

1. Importa una planta PDF, imagen o DXF, o un modelo arquitectónico JSON. En PDF selecciona la página y comprueba la escala en metros por punto PDF; para imágenes, metros por píxel. La escala inicial predeterminada **no está calibrada contra cotas**.
2. Abre **Revisión y archivo**. Corrige extremos, grosor y altura de los muros, y posición, sección y altura de las columnas. Puedes añadir y eliminar esos elementos. Un clic en el elemento 3D lo selecciona en el panel.
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

Los huecos del modelo JSON se representan también en la escena 3D. La edición visual de puertas/ventanas, alzados y secciones, cubiertas, varias plantas y detalles todavía requiere desarrollo adicional. Los colores del visor y las piezas geométricas simples de mobiliario no equivalen a un catálogo de acabados constructivos.

Una malla 3D o una imagen de una casa no contiene necesariamente las capas, espesores, elementos estructurales, instalaciones o detalles ocultos. Para obtener un expediente comparable al elaborado por un arquitecto habrá que interpretar o aportar esos datos, definir formatos y láminas, resolver encuentros y revisar medidas y normativa. Esta entrega no genera un expediente completo, aprobado ni firmado, ni calcula cimentación o instalaciones. Registra esos datos como pendientes y conserva las fuentes para completarlos después.

## Importadores incluidos

El PDF se rasteriza en la página elegida a un píxel por punto PDF. El detector de imágenes es aproximado y no separa automáticamente todas las vistas de una lámina. Se eliminó la invención de puertas/ventanas basada solo en la longitud de un muro y la habitación ficticia formada por el rectángulo envolvente; esas suposiciones no deben alimentar el dataset. Los ambientes se proponen solo con contornos cerrados.

El lector DXF es básico: líneas como ejes de muro y columnas rectangulares alineadas en capas con `COL` o `PILAR`. Lee unidades de la cabecera o exige seleccionarlas si no están declaradas. No interpreta bloques, arcos, capas complejas ni contornos dobles como un importador CAD completo. Las columnas de PDF pueden añadirse y revisarse manualmente; no se ha validado reconocimiento completo de la vivienda real en esta copia.

## Desarrollo

Python 3.12 y Node 20 o superior; validado con Node 24.19.0.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
mkdir -p data/exports/videos
PROJECT_DB="$PWD/data/projects.sqlite3" EXPORT_DIR="$PWD/data/exports" VIDEO_OUTPUT_DIR="$PWD/data/exports/videos" .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

En otra terminal:

```sh
cd frontend
npm ci
npm run dev
```

Vite conserva el prefijo `/api` y dirige las peticiones al backend. La persistencia SQLite incluye archivos binarios y revisiones; `PROJECT_DB` define su ubicación. En Docker, `./data` se monta en `/app/data` para conservarla al recrear el contenedor. Respalda la base con el mecanismo de backup de SQLite y descarga el archivo del proyecto. No elimines el volumen de datos al actualizar.

Esta base tiene un único espacio de trabajo sin autenticación ni separación por clientes. Antes de ofrecer archivos privados a usuarios independientes se necesita añadir cuentas, permisos y aislamiento. El endpoint antiguo de vídeo Celery conserva defectos y no forma parte de la validación de esta entrega; requiere Redis y aún no genera un recorrido real de la escena.

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

## Despliegue

La aplicación no se ha desplegado en DigitalOcean desde este entorno. Con el código transferido al servidor y los datos respaldados, el responsable del despliegue puede validar `docker compose config --quiet`, compilar las imágenes y arrancar los servicios. Los cambios Docker/Nginx preservan `/api/v1` y el volumen de datos; la pila completa de contenedores debe verificarse en destino. El entorno de desarrollo de esta entrega arranca de forma nativa y no necesita Redis para importar, revisar, archivar y exportar modelos.
