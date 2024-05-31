bl_info = {
    'name': 'Rayne Model and Animation Formats (.sgm, .sga)',
    'author': 'EBSpark',
    'version': (2, 0, 0),
    'blender': (4, 1, 0),
    'description': 'Imports .sgm model files and .sga animation files into Blender.',
    'category': 'Import',
    'location': 'File -> Import -> Rayne Model (.sgm, .sga)'
}

import bpy
import struct
import os
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from bpy.props import StringProperty

class SGMFileReader:
    def __init__(self, filename):
        self.filename = filename
        self.magic_number = None
        self.version = None
        self.materials = []
        self.meshes = []
        self.animations = []

    def read(self):
        with open(self.filename, 'rb') as file:
            self.magic_number = struct.unpack('I', file.read(4))[0]
            self.version = struct.unpack('B', file.read(1))[0]

            num_materials = struct.unpack('B', file.read(1))[0]
            for _ in range(num_materials):
                material = self._read_material(file)
                self.materials.append(material)

            num_meshes = struct.unpack('B', file.read(1))[0]
            for _ in range(num_meshes):
                mesh = self._read_mesh(file)
                self.meshes.append(mesh)

            has_animation = struct.unpack('B', file.read(1))[0]
            if has_animation:
                animation = self._read_animation(file)
                self.animations.append(animation)

    def _read_material(self, file):
        material_id = struct.unpack('B', file.read(1))[0]
        num_uv_sets = struct.unpack('B', file.read(1))[0]
        textures = []
        for _ in range(num_uv_sets):
            num_textures = struct.unpack('B', file.read(1))[0]
            for _ in range(num_textures):
                texture_type_hint = struct.unpack('B', file.read(1))[0]
                filename_length = struct.unpack('H', file.read(2))[0]
                filename = file.read(filename_length).decode('utf-8')
                if '*' in filename:
                    model_directory = os.path.dirname(self.filename)
                    files_in_directory = os.listdir(model_directory)
                    for file_in_directory in files_in_directory:
                        if filename.split('*')[0] in file_in_directory:
                            filename = os.path.join(model_directory, file_in_directory).replace('*','png')
                            break
                textures.append((texture_type_hint, filename))

        num_colors = struct.unpack('B', file.read(1))[0]
        colors = []
        for _ in range(num_colors):
            color_type_hint = struct.unpack('B', file.read(1))[0]
            color_rgba = struct.unpack('4f', file.read(16))
            colors.append((color_type_hint, color_rgba))

        return {
            'material_id': material_id,
            'textures': textures,
            'colors': colors,
        }

    def _read_mesh(self, file):
        mesh_id = struct.unpack('B', file.read(1))[0]
        used_material_id = struct.unpack('B', file.read(1))[0]
        num_vertices = struct.unpack('I', file.read(4))[0]
        texcoord_count = struct.unpack('B', file.read(1))[0]
        color_channel_count = struct.unpack('B', file.read(1))[0]
        has_tangents = struct.unpack('B', file.read(1))[0]
        has_bones = struct.unpack('B', file.read(1))[0]

        vertex_data_format = 'fff'  # position
        vertex_data_format += 'fff'  # normal
        vertex_data_format += 'ff' * texcoord_count  # uvs
        if color_channel_count > 0:
            vertex_data_format += 'ffff'  # color
        if has_tangents:
            vertex_data_format += 'ffff'  # tangents
        if has_bones:
            vertex_data_format += 'ffff'  # weights
            vertex_data_format += 'BBBB'  # bone indices

        vertex_size = struct.calcsize(vertex_data_format)
        vertices = [struct.unpack(vertex_data_format, file.read(vertex_size)) for _ in range(num_vertices)]

        num_indices = struct.unpack('I', file.read(4))[0]
        index_size = struct.unpack('B', file.read(1))[0]
        index_format = 'H' if index_size == 2 else 'I'
        indices = [struct.unpack(index_format, file.read(index_size))[0] for _ in range(num_indices)]

        return {
            'mesh_id': mesh_id,
            'used_material_id': used_material_id,
            'vertices': vertices,
            'indices': indices,
        }

    def _read_animation(self, file):
        animfilename_length = struct.unpack('H', file.read(2))[0]
        animfilename = file.read(animfilename_length).decode('utf-8')
        return {
            'animfilename': animfilename,
        }

def create_material(material_data):
    material = bpy.data.materials.new(name=f"Material_{material_data['material_id']}")
    material.use_nodes = True
    bsdf = material.node_tree.nodes["Principled BSDF"]

    for texture_type_hint, texture_filename in material_data['textures']:
        image_texture = material.node_tree.nodes.new('ShaderNodeTexImage')
        image_texture.image = bpy.data.images.load(texture_filename)
        if texture_type_hint == 0:  # Diffuse
            material.node_tree.links.new(bsdf.inputs['Base Color'], image_texture.outputs['Color'])
        elif texture_type_hint == 2:  # Specular
            material.node_tree.links.new(bsdf.inputs['Specular'], image_texture.outputs['Color'])
        elif texture_type_hint == 3:  # Roughness
            material.node_tree.links.new(bsdf.inputs['Roughness'], image_texture.outputs['Color'])

    for color_type_hint, color_rgba in material_data['colors']:
        if color_type_hint == 0:  # Base Color
            bsdf.inputs['Base Color'].default_value = color_rgba
        elif color_type_hint == 2:  # Specular
            bsdf.inputs['Specular'].default_value = color_rgba[0]  
        elif color_type_hint == 3:  # Roughness
            bsdf.inputs['Roughness'].default_value = color_rgba[0]  
            
    return material

def create_mesh(mesh_data, materials):
    mesh = bpy.data.meshes.new(name=f"Mesh_{mesh_data['mesh_id']}")
    obj = bpy.data.objects.new(name=f"Mesh_{mesh_data['mesh_id']}", object_data=mesh)
    bpy.context.collection.objects.link(obj)

    vertices = [v[:3] for v in mesh_data['vertices']]
    indices = mesh_data['indices']

    mesh.from_pydata(vertices, [], [indices[i:i+3] for i in range(0, len(indices), 3)])

    if len(mesh_data['vertices'][0]) > 6:
        uvs = [v[6:8] for v in mesh_data['vertices']]
        uv_layer = mesh.uv_layers.new(name='UVMap')
        mesh.uv_layers.active = uv_layer
        for i, uv in enumerate(uvs):
            uv_layer.data[i].uv = uv

    if len(mesh_data['vertices'][0]) > 8:
        colors = [v[8:12] for v in mesh_data['vertices']]
        color_layer = mesh.vertex_colors.new(name='Col')
        for i, col in enumerate(colors):
            color_layer.data[i].color = col

    used_material_id = mesh_data['used_material_id']
    if used_material_id < len(materials):
        obj.data.materials.append(materials[used_material_id])

class IMPORT_OT_sgm(Operator, ImportHelper):
    bl_idname = "import_scene.sgm"
    bl_label = "Import SGM"
    bl_options = {'PRESET', 'UNDO'}

    filter_glob: StringProperty(
        default="*.sgm;*.sga",
        options={'HIDDEN'},
    )

    def execute(self, context):
        filepath = self.filepath
        import_sgm(filepath)
        return {'FINISHED'}

def import_sgm(filename):
    reader = SGMFileReader(filename)
    reader.read()

    materials = [create_material(mat_data) for mat_data in reader.materials]
    for mesh_data in reader.meshes:
        create_mesh(mesh_data, materials)

def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_sgm.bl_idname, text="Rayne Model (.sgm, .sga)")

def register():
    bpy.utils.register_class(IMPORT_OT_sgm)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_sgm)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
