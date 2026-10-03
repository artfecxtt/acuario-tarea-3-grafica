# Tarea 3 - Maite C. Sánchez Guenante
La presente tarea se trata de una pecera con comportamiento e interacciones pseudo-realistas de peces en un cardumen, con comida y con el hecho de estar confinados dentro de la pecera misma.

## Componentes Técnicos
Se implementó el Modelo de Iluminación de Phong, la Carga de Mallas Complejar (.obj), un Sistema de Colisiones entre peces y con la pecera, Físicas y Cinemática sobre el movimiento y comportamiento de los peces, y Manejo en 3D de todos los ítems anteriores, ya que todos están aplicados en un entorno 3D. Esto, según la tabla de puntajes, daría una sumatoria de 2.0 + 2.0 + 2.0 + 2.0 + 1.0 = 9.0 pts en total.

## Controles
- La cámara se puede mover con el mouse y con las teclas W, A, S, D. Donde W es hacia adelante, S hacia atrás, A hacia la izquierda y D a la derecha.
- Apretando la tecla espacio se pueden spawnear más peces dentro de la pecera.
- Apretando la tecla F se puede spawnear un bloque de comida. Al apretar F nuevamente, la comida desaparece siendo reemplazado por otro bloque dentro de la pecera en una posición aleatoria.

## Uso de IA
Inteligencia Artificial fue usada como guía para la implementación de las funciones de movimiento y fuerzas de interacción que eran de gran complejidad al ser extraídas de los papers citados al final del presente documento. También fue usada como guía para el debuggeo de la tarea una vez implementada.

# Instrucciones de Ejecución
Para ejecutar la tarea correctamente:

## 1. Entorno Virtual (venv)
El archivo del código debe estar **dentro de la carpeta del entorno virtual (`venv`)**.

## 2. Instalación de Dependencias
Antes de correr la tarea, verificar si las librerías necesarias están instaladas (ver archivo `requirements.txt`).

## 3. Ubicación en la terminal
La terminal debe estar en la dirección **exacta** de la carpeta donde se encuentra el archivo tarea-3.py.

## 4. Ejecución
Se ejecuta con `python tarea-3.py`.

## Aclaraciones
La tarea es un poco pesada, al menos mi computador se mantiene aproximadamente 10 a 30 segundos con la ventana en blanco antes de poder mostrar la tarea en pantalla.

# Créditos

## Papers utilizados
- Nguyen, L. T. H., Tạ, T. V., & Yagi, A. (2025). *Mathematical models for fish schooling*. arXiv. https://doi.org/10.48550/arXiv.2508.08310
- Takagi, T., Moritomi, Y., Iwata, J., Nakamine, H., & Sannomiya, N. (2004). Mathematical model of fish schooling behaviour in a set-net. *ICES Journal of Marine Science, 61(7)*, 1214–1223. https://doi.org/10.1016/j.icesjms.2004.07.009

## Modelos Utilizados
Piña
- Fruta de Piña V1 de printable_models.
- https://free3d.com/es/modelo-3d/pineapple-v1--245845.html?dd_referrer=

Coral
- Coral V1 de printable_models.
- https://free3d.com/es/modelo-3d/coral-v1--901825.html?dd_referrer=

Árbol Coral
- Árbol Coral V2 de printable_models.
- https://free3d.com/es/modelo-3d/tree-coral-v2--625204.html?dd_referrer=

Table Coral
- Tabla Coral V2 de printable_models.
- https://free3d.com/es/modelo-3d/table-coral-v2--998917.html?dd_referrer=

Moai
- Moai V3 de printable_models.
- https://free3d.com/es/modelo-3d/moai-v3--808476.html

Pilar
- Pilar de diegotoon20.
- https://free3d.com/es/modelo-3d/pillar-pilar-45905.html

Pescado
- Pescado - Low Poly de needlowpoly.
- https://free3d.com/es/modelo-3d/fish---low-poly-82864.html?dd_referrer=


