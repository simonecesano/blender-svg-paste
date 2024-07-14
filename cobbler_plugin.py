import bpy
import subprocess
import math
import os
import tempfile
import mathutils
import bmesh

# ----------------------------------------
# helper functions for SVG
# ----------------------------------------

def get_current_view_plane(space):
    quat = space.region_3d.view_rotation
    rot_matrix = quat.to_matrix()
    # The third column of the rotation matrix represents the direction of the view
    view_direction = rot_matrix.col[2]

    # Check the view direction to determine the plane view
    if abs(view_direction.dot(mathutils.Vector((0, 0, 1)))) > 0.99:
        return "xy"
    elif abs(view_direction.dot(mathutils.Vector((0, 1, 0)))) > 0.99:
        return "xz"
    elif abs(view_direction.dot(mathutils.Vector((1, 0, 0)))) > 0.99:
        return "yz"
    else:
        return "Non-orthographic"

def import_svg_from_clipboard(view_plane):
    try:
        # Get SVG content from clipboard
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'image/svg+xml', '-o'], stdout=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError("Failed to get clipboard content with xclip")
        svg_content = result.stdout

        # Create a temporary file to save the SVG content
        temp_svg_filepath = None
        with tempfile.NamedTemporaryFile(delete=False, suffix='.svg') as temp_svg_file:
            temp_svg_file.write(svg_content)
            temp_svg_filepath = temp_svg_file.name
            temp_svg_file.close()

        # Import the SVG file into Blender
        start_objects = [ o.name for o in bpy.data.objects ]
        bpy.ops.import_curve.svg(filepath=temp_svg_filepath)
        svg_obj_names = [ o.name for o in bpy.data.objects if o.name not in start_objects ]

        # convert to mesh
        for svg_obj_name in svg_obj_names:
            svg_obj = bpy.data.objects[svg_obj_name]
            bpy.context.view_layer.objects.active = svg_obj
            svg_obj.select_set(True)
            bpy.ops.object.convert(target='MESH')

        if os.path.exists(temp_svg_filepath):
            os.remove(temp_svg_filepath)
            
        bpy.data.collections[os.path.basename(temp_svg_filepath)].name = "Pasted Object"
        return [ o for o in bpy.data.objects if o.name not in start_objects ]
    
    except Exception as e:
        print(f"An error occurred: {e}")

def rotate_svg_onto_plane(svg_obj, view_plane):
    # Adjust orientation based on the view plane
    if view_plane == "xy":
        svg_obj.rotation_euler = (0, 0, 0)
    elif view_plane == "xz":
        svg_obj.rotation_euler = (math.radians(90), 0, 0)
    elif view_plane == "yz":
        svg_obj.rotation_euler = (0, math.radians(90), 0)
    else:
        print("Error: Non-orthographic view")

# ----------------------------------------
# helper functions for patch deform
# ----------------------------------------

def mesh_distance(self, obj):
    """
    calculates the average distance between vertices of two
    meshes
    """
    mesh_a = self
    mesh_b = obj

    total_distance = 0.0
    vertex_count = 0
    average_distance = 0
    
    if mesh_a and mesh_b:
        for vertex_a in mesh_a.data.vertices:
            vertex_a_co_world = mesh_a.matrix_world @ vertex_a.co
            result, location, normal, index = mesh_b.closest_point_on_mesh(vertex_a_co_world)

            distance = (location - vertex_a_co_world).length
            total_distance += distance
            vertex_count += 1
        if vertex_count > 0:
            average_distance = total_distance / vertex_count
                
        # Free the BMesh
    return average_distance


# -------------------------------------------------------
# this swaps the reference meshes to insure that the one
# closest to the projected path is the starting one
# otherwise you have to pay attention to the order
# in which you select them
# -------------------------------------------------------
def patch_deform(ob_a, source_mesh, dest_mesh):
    dist_ab = mesh_distance(ob_a, source_mesh)
    dist_ac = mesh_distance(ob_a, dest_mesh)
    if dist_ab > dist_ac: source_mesh, dest_mesh = [ dest_mesh, source_mesh ]

    ob_a.select_set(True)
    bpy.ops.object.transform_apply()
    ob_a.select_set(False)

    source_mesh.select_set(True)
    bpy.ops.object.transform_apply()
    source_mesh.select_set(False)

    dest_mesh.select_set(True)
    bpy.ops.object.transform_apply()
    dest_mesh.select_set(False)

    bm_a = bmesh.new()
    bm_a.from_mesh(ob_a.data)
    bm_a.verts.ensure_lookup_table()
    print(len(bm_a.verts))
    print(len(ob_a.data.vertices))

    for i, v in enumerate(bm_a.verts):
        # Get the vertex's global coordinates
        # v_co = bm_a.verts[v.index].co
        m_co = bm_a.verts[i].co
        result, location, normal, index = source_mesh.closest_point_on_mesh(m_co)

        if result:
            vt_b = [ source_mesh.data.vertices[v].co for v in source_mesh.data.polygons[index].vertices ]
            vt_c = [ dest_mesh.data.vertices[v].co   for v in dest_mesh.data.polygons[index].vertices ]
            co = mathutils.geometry.barycentric_transform(v.co, vt_b[0], vt_b[1], vt_b[2], vt_c[0], vt_c[1], vt_c[2])
            bm_a.verts[i].co = co
    bm_a.to_mesh(ob_a.data)
    bm_a.free()
            
# ----------------------------------------
# nudge on normals helper functions
# ----------------------------------------

def nudge_obj_on_normals(ob_a, amt):
    bm_a = bmesh.new()
    bm_a.from_mesh(ob_a.data)
    bm_a.verts.ensure_lookup_table()
    for vertex in bm_a.verts:
        vertex.co += 0.006 * vertex.normal
    bm_a.to_mesh(ob_a.data)
    bm_a.free()


# ----------------------------------------
# easy knife helper functions
# ----------------------------------------

def easy_knife_cut_obj(target_obj, cutter_obj):
    area = [area for area in bpy.context.screen.areas if area.type == "VIEW_3D"][0]
    region = [region for region in area.regions if region.type == 'WINDOW'][0]

    with bpy.context.temp_override(area=area, region=region):
        duplicate_obj = target_obj.copy()
        duplicate_obj.data = duplicate_obj.data.copy()

        bpy.context.collection.objects.link(duplicate_obj)
        # Apply any transformations to the duplicate object
        duplicate_obj.matrix_world = target_obj.matrix_world

        bpy.ops.object.select_all(action='DESELECT')
        duplicate_obj.select_set(True)
        bpy.context.view_layer.objects.active=duplicate_obj
        bpy.ops.object.mode_set(mode='EDIT')
        cutter_obj.select_set(True)

        bpy.ops.mesh.knife_project(cut_through=False)
        bpy.ops.mesh.separate(type='SELECTED')

        bpy.data.objects.remove(duplicate_obj, do_unlink=True)

        
# ----------------------------------------
# end of helper functions
# ----------------------------------------

class MyProperties(bpy.types.PropertyGroup):
    flattened: bpy.props.PointerProperty(
        name="Flattened Object",
        type=bpy.types.Object,
        description="Select the flattened object"
    )
    wrapped: bpy.props.PointerProperty(
        name="Wrapped Object",
        type=bpy.types.Object,
        description="Select the wrapped object"
    )

class OBJECT_OT_paste_svg(bpy.types.Operator):
    bl_idname = "object.paste_svg"
    bl_label = "Paste SVG"


    
    def execute(self, context):
        self.paste_svg(context)
        return {'FINISHED'}
    
    def paste_svg(self, context):
        space = None
        try:
            space = [a for a in bpy.context.screen.areas if a.type == "VIEW_3D" ][0].spaces.active
            if space.type == 'VIEW_3D':
                view_plane = get_current_view_plane(space)
                pasted_objs = import_svg_from_clipboard(view_plane)
                for o in pasted_objs:
                    rotate_svg_onto_plane(o, view_plane)        
        except Exception as e:
            print(e)
        print("Paste SVG function called")

class OBJECT_OT_wrap_or_flatten(bpy.types.Operator):
    bl_idname = "object.wrap_or_flatten"
    bl_label = "Wrap or Flatten"
    
    def execute(self, context):
        self.wrap_or_flatten(context)
        return {'FINISHED'}
    
    def wrap_or_flatten(self, context):
        # Stub function for wrapping or flattening
        my_tool = context.scene.my_tool
        flattened_obj = my_tool.flattened
        wrapped_obj = my_tool.wrapped
        print("Wrap or Flatten function called")
        patch_deform(bpy.context.active_object, my_tool.flattened, my_tool.wrapped)
        # Add your code here

class OBJECT_OT_easy_knife_cut(bpy.types.Operator):
    bl_idname = "object.easy_knife_cut"
    bl_label = "Easy Knife Cut"

    def execute(self, context):
        self.easy_knife_cut(context)
        return {'FINISHED'}
    
    def easy_knife_cut(self, context):
        my_tool = context.scene.my_tool
        flattened_obj = my_tool.flattened
        wrapped_obj = my_tool.wrapped
        cutting_obj = bpy.context.active_object

        easy_knife_cut_obj(wrapped_obj, cutting_obj)

        # Stub function for easy knife cutting
        print("Easy Knife Cut function called")
        # Add your code here

class OBJECT_OT_nudge_on_normal(bpy.types.Operator):
    bl_idname = "object.nudge_on_normal"
    bl_label = "Nudge on Normal"
    
    def execute(self, context):
        self.nudge_on_normal(context)
        return {'FINISHED'}
    
    def nudge_on_normal(self, context):
        # Stub function for nudging on an normal
        print("Nudge on Normal function called")
        nudge_obj_on_normals(bpy.context.active_object, 0.0006)

        # Add your code here

class OBJECT_PT_cobbler_panel(bpy.types.Panel):
    bl_label = "Cobbler"
    bl_idname = "OBJECT_PT_cobbler_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        my_tool = scene.my_tool
        
        layout.prop(my_tool, "flattened")
        layout.prop(my_tool, "wrapped")
        
        layout.operator("object.paste_svg")
        layout.operator("object.wrap_or_flatten")
        layout.operator("object.easy_knife_cut")
        layout.operator("object.nudge_on_normal")

def register():
    bpy.utils.register_class(MyProperties)
    bpy.types.Scene.my_tool = bpy.props.PointerProperty(type=MyProperties)
    bpy.utils.register_class(OBJECT_OT_paste_svg)
    bpy.utils.register_class(OBJECT_OT_wrap_or_flatten)
    bpy.utils.register_class(OBJECT_OT_easy_knife_cut)
    bpy.utils.register_class(OBJECT_OT_nudge_on_normal)
    bpy.utils.register_class(OBJECT_PT_cobbler_panel)

def unregister():
    bpy.utils.unregister_class(MyProperties)
    del bpy.types.Scene.my_tool
    bpy.utils.unregister_class(OBJECT_OT_paste_svg)
    bpy.utils.unregister_class(OBJECT_OT_wrap_or_flatten)
    bpy.utils.unregister_class(OBJECT_OT_easy_knife_cut)
    bpy.utils.unregister_class(OBJECT_OT_nudge_on_normal)
    bpy.utils.unregister_class(OBJECT_PT_cobbler_panel)

if __name__ == "__main__":
    register()
