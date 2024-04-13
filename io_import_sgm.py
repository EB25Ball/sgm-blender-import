bl_info = {
    'name': 'Rayne Model and Animation Formats (.sgm, .sga)',
    'author': 'EBSpark',
    'version': (1, 0, 0),
    'blender': (4, 1, 0),
    'description': 'Imports .sgm model files and .sga animation files into Blender.',
    'category': 'Import',
    'location': 'File -> Import -> Rayne Model (.sgm, .sga)'
}

import struct
import bpy

def parse_sgm_file(filename):
    with open(filename, "rb") as file:
        magic_number = struct.unpack('<L', file.read(4))[0]
        if magic_number != 352658064:
            raise ValueError("Invalid magic number, not an sgm file")
        version = struct.unpack('<B', file.read(1))[0]
        print(f"File format version: {version}")

        num_materials = struct.unpack('<B', file.read(1))[0]
        materials = []
        for _ in range(num_materials):
            material_id = struct.unpack('<B', file.read(1))[0]
            uv_count = struct.unpack('<B', file.read(1))[0]
            uv_data = []
            for _ in range(uv_count):
                image_count = struct.unpack('<B', file.read(1))[0]
                images = []
                for _ in range(image_count):
                    usage_hint = struct.unpack('<B', file.read(1))[0]
                    texname_len = struct.unpack('<H', file.read(2))[0] - 1
                    texname = struct.unpack(f'<{texname_len}s', file.read(texname_len))[0].decode("utf_8")
                    print(texname,image_count,"image count")
                    file.seek(1, 1) # skip null terminator
                    images.append((texname, usage_hint))
                uv_data.append(images)
            color_count = struct.unpack('<B', file.read(1))[0]
            colors = []
            for _ in range(color_count):
                color_id = struct.unpack('<B', file.read(1))[0]
                color = struct.unpack('<ffff', file.read(16))
                colors.append((color, color_id))
            materials.append({
                'material_id': material_id,
                'uv_data': uv_data,
                'colors': colors
            })
            print(color_count, "counting the colors")

        num_meshes = struct.unpack('<B', file.read(1))[0]
        meshes = [] 
        for _ in range(num_meshes):
            vertices = []
            indices = []
            mesh_id = struct.unpack('<B', file.read(1))[0]
            material_id = struct.unpack('<B', file.read(1))[0]
            vertex_count = struct.unpack('<I', file.read(4))[0]

            uv_count = struct.unpack('<B', file.read(1))[0]
            texdata_count  = struct.unpack('<B', file.read(1))[0]
            
            has_tangents = struct.unpack('<B', file.read(1))[0]
            has_bones = struct.unpack('<B', file.read(1))[0]
            print(vertex_count,uv_count)
            for _ in range(vertex_count):
                position = struct.unpack('<fff', file.read(12))
                normal = struct.unpack('<fff', file.read(12))
                uvs = [struct.unpack('<ff', file.read(8)) for _ in range(uv_count)]
                color = struct.unpack('<ffff', file.read(16)) if texdata_count  == 4 else None
                tangent = struct.unpack('<fff', file.read(12)) if has_tangents else None
                weights = None
                bone_indices = None
                if has_bones:
                    weights = struct.unpack('<ffff', file.read(16))
                    bone_indices = struct.unpack('<IIII', file.read(16))
                vertex_data = {
                    'position': position,
                    'normal': normal,
                    'uvs': uvs,
                    'color': color,
                    'tangents': tangent,
                    'weights': weights,
                    'bone_indices': bone_indices
                }
                vertices.append(vertex_data)

            index_count = struct.unpack('<I', file.read(4))[0]
            index_size = struct.unpack('<B', file.read(1))[0]            
            indices_format = '<I' if index_size == 4 else '<H'
            indices = [struct.unpack(indices_format, file.read(index_size))[0] for _ in range(index_count)]
            meshes.append({'id': mesh_id, 'material_id': material_id, 'vertices': vertices, 'indices': indices})
    return meshes, materials

def create_blender_objects(materials, meshes):
    for material in materials:
        mat = bpy.data.materials.new(name=f"Material_{material['material_id']}")        
        for color in material['colors']:
            if color[0] == 0:  # Assuming 0 is the type hint for diffuse color
                mat.diffuse_color = color[1]
        
        for uv_data in material['uv_data']:
            for image in uv_data:
                # Load the image
                img = bpy.data.images.load(image[1])
                
                # Create a texture and assign the image
                tex = bpy.data.textures.new(name=f"Texture_{image[1]}", type='IMAGE')
                tex.image = img
                
                # Add the texture to the material
                mat_tex_slot = mat.texture_slots.add()
                mat_tex_slot.texture = tex

    for mesh_data in meshes:
        mesh = bpy.data.meshes.new(name=f"Mesh_{mesh_data['id']}")
        obj = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        verts = [v['position'] for v in mesh_data['vertices']]
        faces = [tuple(mesh_data['indices'][i:i+3]) for i in range(0, len(mesh_data['indices']), 3)]
        mesh.from_pydata(verts, [], faces)
        obj.data.materials.append(bpy.data.materials[f"Material_{mesh_data['material_id']}"])

class ImportSGM(bpy.types.Operator):
    """Import an SGM file"""
    bl_idname = "import_scene.sgm"
    bl_label = "Import SGM"
    bl_options = {'PRESET', 'UNDO'}
    
    filename_ext = ".sgm"

    filter_glob: bpy.props.StringProperty(
        default="*.sgm;*.sga",
        options={'HIDDEN'},
        maxlen=255,
    )
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        meshes,materials  = parse_sgm_file(self.filepath)
        create_blender_objects(materials, meshes)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def menu_func_import(self, context):
    self.layout.operator(ImportSGM.bl_idname, text="Rayne Model (.sgm)")

def register():
    bpy.utils.register_class(ImportSGM)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(ImportSGM)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
