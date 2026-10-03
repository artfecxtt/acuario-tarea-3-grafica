import pyglet
from pyglet.gl import *
from pyglet.app import run
from pyglet import math
from pyglet import clock
from pyglet.math import Mat4, Vec3
from pyglet.window import Window
from pyglet.window import key
from pyglet.graphics.shader import Shader, ShaderProgram
import trimesh as tm
import grafica.transformations as tr
from utils import colliders

import numpy as np
import os
import sys

#MODULOS (cuidado con las rutas)
sys.path.append(os.path.dirname(os.path.dirname((os.path.dirname(__file__)))))
from utils.helpers import init_axis, mesh_from_file
from utils.camera import FreeCamera
from utils.scene_graph import SceneGraph
from utils import shapes
from utils.drawables import Texture, Model, DirectionalLight, Material, PointLight

#Controller
class Controller(pyglet.window.Window):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.time = 0
        self.light_mode = False
        # le entregamos el manager de colisiones al controlador para
        # tenerlo como una variable globalizada dentro de la ejecución
        # del programa
        self.manager = colliders.CollisionManager()

#CAMARA definida en una clase
# misma cámara de auxs y clases
class MyCam(FreeCamera):
    def __init__(self, position=np.array([0, 0, 0]), camera_type="perspective"):
        super().__init__(position, camera_type)
        self.direction = np.array([0,0,0])
        self.speed = 2

    def time_update(self, dt):
        self.update()
        dir = self.direction[0]*self.forward + self.direction[1]*self.right
        dir_norm = np.linalg.norm(dir)
        if dir_norm:
            dir /= dir_norm
        self.position += dir*self.speed*dt
        self.focus = self.position + self.forward

#clase que controla la simulación de las físicas del cardumen
class Cardumen:
    def __init__(self, graph, mesh, pipeline, num_initial=10):
        self.graph = graph #grafo de escena
        self.mesh = mesh #malla del pez
        self.pipeline = pipeline #pipeline a utilizar
        self.fish_count=0 #total de peces creados

        self.alpha = 1.0 #escala para fuerza atracción o repulsión de peces
        self.beta = 0.5 #escala para la fuerza de alineación
        self.alpha_3 = 5.5 #factor de fuerza de atracción a la comida
        self.r = 0.3 # radio de referencia para las distancias del cardumen
        self.p = 1.3 #potencia de la repulsión y atracción
        self.q = 1 #potencia de la ec del cardumen
        self.v_max = 1.5 #velocidad max de los peces (o si no aceleran mucho)
        self.v_min = 0.3 #velocidad mínima para q no se queden quietos de la nada

        self.positions = [] #posiciones de cada pez en la escena
        self.velocities = [] #velocidad de cada pez en la escena
        self.fish_names = [] #nombre de cada pez en el grafo
        self.fish_colliders = [] #bounding box de cada pez en la escena

        self.food_pos = np.array([0.0, 0.0, 0.0]) #coordenadas actuales de la comida
        self.food_active = False #si es que la comida está o no spawneada

        for _ in range(num_initial): #spawneo de peces iniciales
            self.spawn_fish() 

    # resolución y respuesta de colisiones entre peces y pez-pecera
    # método para resolver colisiones de manera a posteriori
    # basada en el aux 10
    def resolve_collision(self, colliders_list, idx_pez):
        #se coloca cada caja de colisión en la posición dnde está el pez en ese momento
        self.fish_colliders[idx_pez].set_position(self.positions[idx_pez])

        for collider in colliders_list:
            # si en el intertanto ya no colisionan, se ignora
            if not collider.detect_collision(self.fish_colliders[idx_pez]):
                continue

            # calculamos las distancias de penetración en los extremos de las cajas
            d1 = collider.min - self.fish_colliders[idx_pez].max
            d2 = collider.max - self.fish_colliders[idx_pez].min

            # Elegimos la distancia más corta por cada eje
            dist = d1 if np.linalg.norm(d1) < np.linalg.norm(d2) else d2

            # Buscamos cuál es el eje de mínima penetración para corregir solo esa componente
            min_dist = abs(dist[0])
            desplz = np.array([dist[0], 0.0, 0.0])

            eje = 0 # eje donde ocurre la colisión
            for i in range(3):
                t = abs(dist[i])
                if t < min_dist:
                    min_dist = t
                    desplz = np.zeros(3)
                    desplz[i] = dist[i]
                    eje = i

            # corregimos la posición de manera inmediata (a posteriori)
            self.positions[idx_pez] += desplz
            self.velocities[idx_pez][eje] *= -0.8
            # sincronizamos inmediatamente el collider para el siguiente bloque de la lista
            self.fish_colliders[idx_pez].set_position(self.positions[idx_pez])

    # función para spawnear los peces
    def spawn_fish(self):
        self.fish_count += 1
        name = f"fish_{self.fish_count}"

        #posición random dentro de la pecera
        pos = np.array([np.random.uniform(-2.0, 2.0), 
                        np.random.uniform(1.3, 2.0), 
                        np.random.uniform(-2.0, 2.0)])
        vel = np.array([np.random.uniform(-0.5, 0.5), 0.0, np.random.uniform(-0.5, 0.5)])

        # creación de collider
        collider = colliders.AABB(name, [-0.1, -0.1, -0.1], [0.1, 0.1, 0.1])
        controller.manager.add_collider(collider)

        # guardamos datos del neuvo pez
        self.positions.append(pos)
        self.velocities.append(vel)
        self.fish_names.append(name)
        self.fish_colliders.append(collider)

        # añadimos pez al grafo
        self.graph.add_node(name, attach_to="scene",
                                       mesh=self.mesh, color=shapes.BROWN,
                                       pipeline=self.pipeline,
                                       scale=[0.15, 0.15, 0.15],
                                       position=list(pos), 
                                       material=Material(diffuse=[245/255, 39/255, 101/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0))
        
        self.graph.update()

    # función para spawnear comida en la escena
    def spawn_food(self, cube_mesh):

        #solo puede haber una comida en el mapa
        if self.food_active:
            self.remove_food()

        # definimos márgenes aleatorios dentro de la pecera virtual
        self.food_pos = np.array([np.random.uniform(-2.0, 2.0), 
                                  np.random.uniform(0.1, 1.2), 
                                  np.random.uniform(-2.0, 2.0)])
        self.food_active = True

        # si es que ya había comida la posiciona nuevamente para que parezca en otro lugar
        # si no había comida, entoces tira un KeyError y añade el nodo al grafo
        try:
            self.graph["food"]["position"] = list(self.food_pos)
            self.graph["food"]["scale"] = [0.05, 0.05, 0.05]
        except KeyError:
            # Si no existía en el grafo (primera vez que apretamos F), lo creamos
            self.graph.add_node("food", attach_to="scene",
                                       mesh=cube_mesh, color=shapes.RED,
                                       pipeline=self.pipeline,
                                       scale=[0.05, 0.05, 0.05],
                                       position=list(self.food_pos), 
                                       material=Material(diffuse=[1.0, 0, 0], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0))
        self.graph.update()

    # función para eliminar comida de la escena (cuando un pez la come)
    def remove_food(self):
        self.food_active = False

        # se reescala a 0 y se posiciona fuera de rango
        # si no había comida en la escena, se tira un KeyError y se pasa
        try:
            self.graph["food"]["scale"] = [0.0, 0.0, 0.0]
            self.graph["food"]["position"] = [0.0, -10.0, 0.0]
        except KeyError:
            pass
        self.graph.update()
        
    # función que se encarga de TODAS las físicas de los peces y el cardumen
    def update_physics(self, dt):

        N = len(self.positions)
        if N == 0: 
            return

        pos_arr = np.array(self.positions)
        vel_arr = np.array(self.velocities)
        
        new_positions = []
        new_velocities = []

        food_eaten = False

        # cálculo de la fuerza de cohesión del cardumen pez a pez
        for i in range(N):
            #se elige el pez i
            x_i = pos_arr[i]
            v_i = vel_arr[i]
            
            F_cardumen = np.zeros(3)
            vecinos_cercanos = 0 #vecinos cercanos al pez i
            
            # se calculan las distancias del pez i a los otros peces de la pecera
            distancias = []
            for j in range(N):
                if i == j: 
                    continue
                diff_x = x_i - pos_arr[j]
                dist = np.linalg.norm(diff_x)
                if dist < 0.01: 
                    dist = 0.01
                distancias.append((dist, j, diff_x))
            
            # se ordenan las distancias de menor a mayor
            distancias.sort(key=lambda x: x[0])
            
            # limites para que el pez interactúe con los peces más cercanos, max 3, y no con toda la pecera
            # (sin esto, toda la pecera actúa como un cardumen gigante)
            MAX_VECINOS = 3 
            RADIO_VISION = 0.8 


            for dist, j, diff_x in distancias:
                # si es que el pez que revisamos es elcuarto o más, o está muy lejos, se rompe el cálculo
                if vecinos_cercanos >= MAX_VECINOS or dist > RADIO_VISION:
                    break
                
                v_j = vel_arr[j]
                
                # fórmula
                term_p = (self.r ** self.p) / (dist ** self.p)
                term_q = (self.r ** self.q) / (dist ** self.q)
                
                # se multiplica por 0.5 para arreglar un poco que tanto se acercan
                f_att_rep = -self.alpha * (term_p - term_q) * diff_x * 0.5
                f_align = -self.beta * (term_p + term_q) * (v_i - v_j) * 0.3
                
                F_cardumen += (f_att_rep + f_align)
                vecinos_cercanos += 1
            
            # fuerza atracción a la comida
            F_comida = np.zeros(3)
            if self.food_active:
                diff_food = self.food_pos - x_i
                dist_food = np.linalg.norm(diff_food)

                if dist_food < 0.01: 
                    dist_food = 0.01

                # detección de colisión con la comida
                if dist_food < 0.15:
                    food_eaten = True

                # fórmula
                F_comida = self.alpha_3 * (diff_food / dist_food)

            # fuerza de confinamiento: atracción al centro de la pecera para q no quieran escapar
            F_pecera = np.zeros(3)
            diff_pecera = np.array([0.0, 1.7, 0.0]) - x_i
            dist_pecera = np.linalg.norm(diff_pecera) # distancia al centro de la pecera
            if dist_pecera < 0.01: 
                dist_pecera = 0.01

            if dist_pecera > 1.5:
                F_pecera = (dist_pecera-1.4) * (diff_pecera) * 1.6

            # euler
            v_new = v_i + (F_cardumen + F_comida + F_pecera) * dt
            
            # limitación de velocidad
            v_norm = np.linalg.norm(v_new)
            if v_norm > self.v_max:
                v_new = self.v_max * (v_new / v_norm)
            
            if v_norm < self.v_min:
                v_new = self.v_min * (v_new / v_norm)
                
            x_new = x_i + v_new * dt

            self.positions[i] = x_new
            self.velocities[i] = v_new

            # se chequea por colisiones entre peces
            fish_collider = self.fish_colliders[i]
            fish_collider.set_position(self.positions[i])
            check_collisions(self, controller.manager, i)

            x_new = self.positions[i]
            v_new = self.velocities[i]

            new_positions.append(x_new)
            new_velocities.append(v_new)

            # si el pez se mueve, se calcula el ángulo en el plano XZ para que mire al frente
            angle = 0.0
            if np.any(v_new[[0, 2]]):
                angle = np.arctan2(v_new[0], v_new[2])

            fish_key = self.fish_names[i]
            
            # se modifica en el grafo
            self.graph[fish_key]["position"] = list(x_new)
            self.graph[fish_key]["rotation"] = [0.0, angle, 0.0]

        self.positions = new_positions
        self.velocities = new_velocities    

        #sacar comida si es que la tocó un pez
        if food_eaten:
            self.remove_food()

# chequeo de colisiones
def check_collisions(cardumen, manager, idx_fish):
    fish_name = cardumen.fish_names[idx_fish]
    collisions = manager.check_collision(fish_name)
    if not collisions:
        return

    # se resuelven las colisiones con los datos guardados
    cardumen.resolve_collision([manager[b] for b in collisions], idx_fish)

#main
if __name__ == "__main__":

    controller = Controller(1080,920,"Tarea 3")
    controller.set_exclusive_mouse(True)

    # SHADERS
    vertex_source = """
#version 330

in vec3 position;
uniform vec3 u_color = vec3(1.0);


uniform mat4 u_model = mat4(1.0);
uniform mat4 view = mat4(1.0);
uniform mat4 projection = mat4(1.0);

out vec3 fragColor;

void main() {
    fragColor = u_color;
    gl_Position = projection * view * u_model * vec4(position, 1.0f);
}
    """

    fragment_source = """
#version 330

in vec3 fragColor;
out vec4 outColor;

void main()
{
    outColor = vec4(fragColor, 1.0f);
}
    """
    root = os.path.dirname(__file__)

    #Se define el pipeline
    vert_program = pyglet.graphics.shader.Shader(vertex_source, "vertex")
    frag_program = pyglet.graphics.shader.Shader(fragment_source, "fragment")
    pipeline = pyglet.graphics.shader.ShaderProgram(vert_program, frag_program)

    # SHADERS DE ILUMINACIÓN
    with open(root +  "/shaders/color_mesh_lit.vert") as f:
        color_vertex_source_code = f.read()

    with open(root +  "/shaders/color_mesh_lit.frag") as f:
        color_fragment_source_code = f.read()

    vert_program_lit = Shader(color_vertex_source_code, "vertex")
    frag_program_lit = Shader(color_fragment_source_code, "fragment")
    pipeline_lit = pyglet.graphics.shader.ShaderProgram(vert_program_lit, frag_program_lit)

    pipeline_lit["u_dirLight.direction"] = [0.0, -1.0, 0.0]  # luz que apunta directo hacia abajo
    pipeline_lit["u_dirLight.ambient"] = [0.2, 0.2, 0.4]     # tono ambiental
    pipeline_lit["u_dirLight.diffuse"] = [0.7, 0.7, 0.8]
    pipeline_lit["u_dirLight.specular"] = [0.6, 0.6, 0.6]

    #inicialización
    pipeline_lit["u_numPointLights"] = 0
    pipeline_lit["u_numSpotLights"] = 0
    pipeline_lit["u_material.ambient"] = [1.0, 1.0, 1.0]
    pipeline_lit["u_material.diffuse"] = [1.0, 1.0, 1.0]
    pipeline_lit["u_material.specular"] = [0.4, 0.4, 0.4]
    pipeline_lit["u_material.shininess"] = 32.0

    root = os.path.dirname(__file__)

    cam = MyCam([0,0,2])

    # INSERCIÓN DE ASSETS
    BASE_DIR = os.path.dirname(__file__)
    fish_path = os.path.join(BASE_DIR, "assets", "fish", "obj", "fish.obj")
    fish_mesh = mesh_from_file(fish_path)[0]['mesh']

    pilar_path = os.path.join(BASE_DIR, "assets", "pilar", "pilar.obj")
    pilar_mesh = mesh_from_file(pilar_path)[0]['mesh']

    pina_path = os.path.join(BASE_DIR, "assets", "piña", "10200_Pineapple_v1-L2.obj")
    pina_mesh = mesh_from_file(pina_path)[0]['mesh']

    coral_path = os.path.join(BASE_DIR, "assets", "coral", "10010_Coral_v1_L3.obj")
    coral_mesh = mesh_from_file(coral_path)[0]['mesh']

    tree_coral_path = os.path.join(BASE_DIR, "assets", "tree-coral", "21488_Tree_Coral_v2_NEW.obj")
    tree_coral_mesh = mesh_from_file(tree_coral_path)[0]['mesh']

    table_coral_path = os.path.join(BASE_DIR, "assets", "table-coral", "20940_Table_Coral_v2.obj")
    table_coral_mesh = mesh_from_file(table_coral_path)[0]['mesh']

    moai_path = os.path.join(BASE_DIR, "assets", "moai", "10805_Moai_L3.mb.obj")
    moai_mesh = mesh_from_file(moai_path)[0]['mesh']

    cube = Model(shapes.Cube["position"], index_data=shapes.Cube["indices"], normal_data=shapes.Cube["normal"])

    #Grafo de escena
    graph = SceneGraph(cam)
    graph.add_node("scene")

    # creación de la arena del suelo con lo usado en un aux
    n = 50
    base_size = 5.0  # el suelo e sun 5x5
    step = base_size / (n - 1)

    vertices = []
    normals = []

    # vértices centrados en el origen
    for i in range(n):
        for j in range(n):
            x = -base_size / 2.0 + j * step
            z = -base_size / 2.0 + i * step
            vertices += [x, 0.0, z]
            normals += [0.0, 1.0, 0.0]

    # índices para los triángulos
    indices = []
    for i in range(n-1):
        for j in range(n-1):
            indices += [n*(i+1) + j + 1, n*i + j + 1, n * i + j]
            indices += [n*(i+1) + j, n*(i+1) + j + 1, n * i + j]

    # ruido
    for i in range(n * n * 2):
        vertices[np.random.randint(0, n*n) * 3 + 1] += 0.05
    
    for i in range(n * n):
        vertices[np.random.randint(0, n*n) * 3 + 1] += 0.08

    # procesanmiento y suavización de malla
    tri = tm.Trimesh(
        vertices=np.array(vertices).reshape(len(vertices)//3, 3), 
        faces=np.array(indices).reshape(len(indices)//3, 3), 
        process=False
    )
    
    # filtro para el ruido
    tri = tm.smoothing.filter_humphrey(tri)

    # transformar datos
    verticesT = np.array(tri.vertices, dtype=np.float32).flatten()
    facesT = np.array(tri.faces, dtype=np.uint32).flatten()  # <-- Cambiado a uint32 para índices
    normalT = np.array(tri.vertex_normals, dtype=np.float32).flatten()

    uvs = []
    for i in range(n):
        for j in range(n):
            uvs += [0.0, 0.0] 
            
    # mesh
    suelo_mesh = Model(verticesT, normal_data=normalT, index_data=facesT, uv_data=uvs)

    # agregar al grafo
    graph.add_node("floor_mesh", attach_to="floor", 
                   mesh=suelo_mesh, 
                   pipeline=pipeline_lit, 
                   position=[0, 0, 0], 
                   scale=[1, 1, 1], 
                   material=Material(
                       ambient=[0.35, 0.25, 0.15], # Tono café/arena oscuro para las sombras
                       diffuse=[0.76, 0.65, 0.50], # Color arena de playa iluminada
                       specular=[0.1, 0.1, 0.1],   # La arena casi no brilla
                       shininess=4.0
                   ))

    # luz en el grafo
    graph.add_node("luz",
                   pipeline=pipeline_lit,
                   light=DirectionalLight(ambient=[0.8, 0.8, 0.8]),
                   rotation=[-np.pi/2, 0, 0])

    graph.add_node("floor", attach_to="scene")
    #graph.add_node("grass", attach_to="floor",
    #                        mesh=cube, color=shapes.CYAN,
    #                        pipeline=pipeline,
    #                        scale=[5, 0.01, 5],
    #                        position=[0, 0, 0], 
    #                        material=Material(diffuse=[150/255, 188/255, 255/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
    #                    )
    
    # elementos decorativos del fondo de la pecera
    graph.add_node("decorations", attach_to="floor")
    graph.add_node("piña", attach_to="decorations",
                            mesh=pina_mesh, color=shapes.YELLOW,
                            pipeline=pipeline_lit,
                            rotation=[-90, 0, 0],
                            scale=[0.2, 0.2, 0.2],
                            position=[2, 0.35, 1], 
                            material=Material(diffuse=[194/255, 212/255, 42/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    graph.add_node("moai", attach_to="decorations",
                            mesh=moai_mesh, color=shapes.MAGENTA,
                            pipeline=pipeline_lit,
                            rotation=[180, 0, 0],
                            scale=[1, 1, 1],
                            position=[0.5, 0.35, 1], 
                            material=Material(diffuse=[145/255, 145/255, 145/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    graph.add_node("coral", attach_to="decorations",
                            mesh=coral_mesh, color=shapes.MAGENTA,
                            pipeline=pipeline_lit,
                            rotation=[180, 0, 0],
                            scale=[1, 1, 1],
                            position=[-1, 0.25, -1], 
                            material=Material(diffuse=[255/255, 107/255, 222/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    graph.add_node("coral2", attach_to="decorations",
                            mesh=coral_mesh, color=shapes.ORANGE,
                            pipeline=pipeline_lit,
                            rotation=[180, 0, 0],
                            scale=[1, 1, 1],
                            position=[1.8, 0.25, 1.3], 
                            material=Material(diffuse=[232/255, 156/255, 12/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    graph.add_node("coral3", attach_to="decorations",
                            mesh=coral_mesh, color=shapes.ORANGE,
                            pipeline=pipeline_lit,
                            rotation=[180, 0, 0],
                            scale=[1, 1, 1],
                            position=[2, 0.3, -1], 
                            material=Material(diffuse=[232/255, 156/255, 12/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    graph.add_node("coral4", attach_to="decorations",
                            mesh=coral_mesh, color=shapes.GREEN,
                            pipeline=pipeline_lit,
                            rotation=[180, 0, 0],
                            scale=[1, 1, 1],
                            position=[0, 0.3, -0.5], 
                            material=Material(diffuse=[63/255, 204/255, 77/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    graph.add_node("coral5", attach_to="decorations",
                            mesh=coral_mesh, color=shapes.GREEN,
                            pipeline=pipeline_lit,
                            rotation=[180, 0, 0],
                            scale=[1, 1, 1],
                            position=[1.5, 0.25, 1.7],
                            material=Material(diffuse=[63/255, 204/255, 77/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    graph.add_node("table-coral", attach_to="decorations",
                            mesh=table_coral_mesh, color=shapes.BLUE,
                            pipeline=pipeline_lit,
                            rotation=[90, 0, 0],
                            scale=[0.1, 0.1, 0.3],
                            position=[2, 0.3, -0.5], 
                            material=Material(diffuse=[50/255, 55/255, 120/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    graph.add_node("table-coral2", attach_to="decorations",
                            mesh=table_coral_mesh, color=shapes.BLUE,
                            pipeline=pipeline_lit,
                            rotation=[90, 0, 0],
                            scale=[0.1, 0.1, 0.3],
                            position=[0, 0.3, 0], 
                            material=Material(diffuse=[50/255, 55/255, 120/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    graph.add_node("tree-coral", attach_to="decorations",
                            mesh=tree_coral_mesh, color=shapes.GREEN,
                            pipeline=pipeline_lit,
                            scale=[0.8, 0.8, 0.8],
                            position=[-1, 0.35, 1], 
                            material=Material(diffuse=[63/255, 204/255, 77/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    graph.add_node("tree-coral2", attach_to="decorations",
                            mesh=tree_coral_mesh, color=shapes.DARK_BLUE,
                            pipeline=pipeline_lit,
                            rotation=[0, 45, 0],
                            scale=[0.8, 0.8, 0.8],
                            position=[-1, 0.35, 1.5], 
                            material=Material(diffuse=[27/255, 28/255, 66/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    graph.add_node("tree-coral3", attach_to="decorations",
                            mesh=tree_coral_mesh, color=shapes.RED,
                            pipeline=pipeline_lit,
                            scale=[0.8, 0.8, 0.8],
                            position=[1.5, 0.3, -0.5], 
                            material=Material(diffuse=[222/255, 18/255, 45/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    graph.add_node("tree-coral4", attach_to="decorations",
                            mesh=tree_coral_mesh, color=shapes.RED,
                            pipeline=pipeline_lit,
                            scale=[0.8, 0.8, 0.8],
                            position=[-1.2, 0.25, -1.5], 
                            material=Material(diffuse=[222/255, 18/255, 45/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0)
                        )
    
    piso_collider = colliders.AABB("piso", [-2.5, -10, -2.5], [2.5, 0.01, 2.5])
    controller.manager.add_collider(piso_collider)

    #graph.add_node("paredes", attach_to="floor")
    #graph.add_node("pared_izq", attach_to="paredes", 
    #               mesh=cube, color=shapes.WHITE, 
    #               pipeline=pipeline, 
    #               scale=[0, 4, 5], 
    #               position=[-2.5, 1.7, 0])
    
    pared_izq_collider = colliders.AABB("pared_izq", [-10, -0.3, -2.5], [-2.45, 3.7, 2.5])
    controller.manager.add_collider(pared_izq_collider)

    #graph.add_node("pared_der", attach_to="paredes", 
    #               mesh=cube, color=shapes.WHITE, 
    #               pipeline=pipeline, 
    #               scale=[0, 4, 5], 
    #               position=[2.5, 1.7, 0])
    
    pared_der_collider = colliders.AABB("pared_der", [2.45, -0.3, -2.5], [10, 3.7, 2.5])
    controller.manager.add_collider(pared_der_collider)

    #graph.add_node("pared_fondo", attach_to="paredes", 
    #               mesh=cube, color=shapes.WHITE, 
    #               pipeline=pipeline, 
    #               scale=[5, 4, 0], 
    #               position=[0, 1.7, -2.5])
    
    pared_fondo = colliders.AABB("pared_fondo", [-2.5, -0.3, -10], [2.5, 3.7, -2.4])
    controller.manager.add_collider(pared_fondo)

    #graph.add_node("pared_frente", attach_to="paredes", 
    #               mesh=cube, color=shapes.WHITE, 
    #               pipeline=pipeline, 
    #               scale=[5, 4, 0], 
    #               position=[0, 1.7, 2.5])
    
    pared_frente = colliders.AABB("pared_frente", [-2.5, -0.3, 2.45], [2.5, 3.7, 10])
    controller.manager.add_collider(pared_frente)

    #graph.add_node("techo", attach_to="paredes",
    #                        mesh=cube, color=shapes.GREEN,
    #                        pipeline=pipeline,
    #                        scale=[5, 0.01, 5],
    #                        position=[0, 3.5, 0]
    #                    )
    
    techo_collider = colliders.AABB("techo", [-2.5, 3.5, -2.5], [2.5, 10, 2.5])
    controller.manager.add_collider(techo_collider)

    #pilares de la pecera
    graph.add_node("pilares", attach_to="floor")
    graph.add_node("pilar_1", attach_to="pilares", 
                   mesh=pilar_mesh, color=shapes.LIGHT_BLUE,
                   pipeline=pipeline_lit, 
                   scale = [1, 2, 1], 
                   position=[-2.5, 1.9, -2.5], 
                   material=Material(diffuse=[166/255, 199/255, 224/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0))
    graph.add_node("pilar_2", attach_to="pilares", 
                   mesh=pilar_mesh, color=shapes.LIGHT_BLUE,
                   pipeline=pipeline_lit, 
                   scale = [1, 2, 1], 
                   position=[-2.5, 1.9, 2.5], 
                   material=Material(diffuse=[166/255, 199/255, 224/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0))
    graph.add_node("pilar_3", attach_to="pilares", 
                   mesh=pilar_mesh, color=shapes.LIGHT_BLUE,
                   pipeline=pipeline_lit, 
                   scale = [1, 2, 1], 
                   position=[2.5, 1.9, 2.5], 
                   material=Material(diffuse=[166/255, 199/255, 224/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0))
    graph.add_node("pilar_4", attach_to="pilares", 
                   mesh=pilar_mesh, color=shapes.LIGHT_BLUE,
                   pipeline=pipeline_lit, 
                   scale = [1, 2, 1], 
                   position=[2.5, 1.9, -2.5], 
                   material=Material(diffuse=[166/255, 199/255, 224/255], ambient=[0.2, 0.2, 0.2], specular=[0.5, 0.5, 0.5], shininess=32.0))
    
    #pared_fondo_izq = colliders.AABB("pared_fondo_izq", [-2.5, -0.5, -2.5], [-2.5, 0.01, 2.5])
    #controller.manager.add_collider(piso_collider)

    cardumen = Cardumen(graph, fish_mesh, pipeline_lit, num_initial=10)

    #graph.add_node("food", attach_to="scene",
    #                       mesh=cube, color=shapes.RED,
    #                       pipeline=pipeline,
    #                       scale=[0.05, 0.05, 0.05],
    #                       position=list(cardumen.food_pos))
    
    #Matriz perspectiva
    pipeline["projection"] = pyglet.math.Mat4.perspective_projection(800/600, 0.01, 100, 100)

    @controller.event
    def on_draw():
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glClearColor(0.1, 0.1, 0.1, 0.0)
        
        controller.clear()

        pipeline["view"] = cam.get_view()

        #Dibuje el grafo
        graph.draw()

    @controller.event
    def on_key_press(symbol, modifiers):
        if symbol == key.W:
            cam.direction[0] = 1
        if symbol == key.S:
            cam.direction[0] = -1

        if symbol == key.A:
            cam.direction[1] = 1
        if symbol == key.D:
            cam.direction[1] = -1

        #se spawnea un pez con espacio
        if symbol == key.SPACE:
            cardumen.spawn_fish()
        #se spawnea un comida con F
        if symbol == key.F:
            cardumen.spawn_food(cube)

    @controller.event
    def on_key_release(symbol, modifiers):
        if symbol == key.W or symbol == key.S:
            cam.direction[0] = 0

        if symbol == key.A or symbol == key.D:
            cam.direction[1] = 0

    @controller.event
    def on_mouse_motion(x, y, dx, dy):
        cam.yaw += dx * .001
        cam.pitch += dy * .001
        cam.pitch = math.clamp(cam.pitch, -(np.pi/2 - 0.01), np.pi/2 - 0.01)

    #informacion que se actualiza con el tiempo
    def update(dt):
        cardumen.update_physics(dt)
        cam.time_update(dt)
        graph.update()

        c_pos = cam.position.copy()
        c_pos[1] = 0

        controller.time += dt

    pyglet.clock.schedule_interval(update, 1/60)
    pyglet.app.run()
    