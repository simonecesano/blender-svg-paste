import bpy
import subprocess
import math
import sys
import os
import tempfile
import mathutils
import bmesh
import shapely

if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import triangulate

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

# --------------------------------------------------------------------------
        
class SVGPasteSettings(bpy.types.PropertyGroup):
    convert_to_mesh_after_pasting: bpy.props.BoolProperty(
        name="Convert to Curve After Pasting",
        description="Convert to curve after pasting SVG",
        default=False
    )
    triangulate_after_pasting: bpy.props.BoolProperty(
        name="Triangulate After Pasting",
        description="Triangulate after pasting SVG",
        default=False
    )
    triangulation_method: bpy.props.EnumProperty(
        name="Triangulation Method",
        description="Method for triangulation",
        items=[
            ('RANDOM_POINTS_SAMPLING', "Random triangles", ""),
            ('UNIFORM_GRID_SAMPLING', "Grid", ""),
            ('HEXAGONAL_GRID_SAMPLING', "Hexagons", ""),
            # ('POISSON_DISC_SAMPLING', "Poisson discs", ""), # slow af
            ('BLUE_NOISE_SAMPLING', "Blue noise", ""),
            ('CENTROID_SAMPLING', "Centroids", "")
        ],
        default='CENTROID_SAMPLING'
    )
    triangulation_points: bpy.props.IntProperty(
        name="Triangulation points",
        description="Number of triangulation points",
        default=1000
    )
    keep_original: bpy.props.BoolProperty(
        name="Keep Original",
        description="Keep the original object",
        default=False
    )
    target: bpy.props.PointerProperty(
        name="Target",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type in {'MESH', 'CURVE'}
    )

class OBJECT_PT_SVGPastePanel(bpy.types.Panel):
    bl_label = "SVG Paste"
    bl_idname = "OBJECT_PT_svg_paste_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SVG Paste'

    def draw(self, context):
        layout = self.layout
        svg_paste = context.scene.svg_paste

        # Boolean inputs
        layout.prop(svg_paste, "convert_to_mesh_after_pasting")
        layout.prop(svg_paste, "triangulate_after_pasting")

        # Dropdown for triangulation method
        layout.label(text="Triangulation method:")        
        layout.prop(svg_paste, "triangulation_method", text="")

        # Button to paste SVG
        layout.operator("object.paste_svg", text="Paste SVG")

        # Boolean input for keep_original, numper of points
        layout.prop(svg_paste, "keep_original")
        layout.prop(svg_paste, "triangulation_points")

        layout.separator()
        # Button to convert to curve
        layout.operator("object.convert_to_mesh", text="Convert to Curve")

        # Button to triangulate
        layout.operator("object.triangulate", text="Triangulate")

        layout.separator()

        # Picker for target object
        layout.prop(svg_paste, "target")

        # Button to align and resize
        layout.operator("object.align_and_resize", text="Align and Resize")

class OBJECT_OT_PasteSVG(bpy.types.Operator):
    bl_idname = "object.paste_svg"
    bl_label = "Paste SVG"

    def execute(self, context):
        self.paste_svg(context)
        return {'FINISHED'}

    def paste_svg(self, context):
        svg_paste = context.scene.svg_paste
        # Placeholder function for pasting SVG
        print("Pasting SVG...")
        # Your code to paste SVG goes here
    
        space = None
        pasted_objs = []
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

        print(pasted_objs)
        
        if svg_paste.convert_to_mesh_after_pasting:
            start_objects = [ o.name for o in bpy.data.objects ]
            for obj in pasted_objs:
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.convert(target='MESH')
                # Call convert_to_mesh function
            pasted_objs = [ o for o in bpy.data.objects if o.name not in start_objects ]

        if svg_paste.triangulate_after_pasting:
            start_objects = [ o.name for o in bpy.data.objects ]
            pasted_objs = [ o for o in bpy.data.objects if o.name not in start_objects ]


            pass
            # Call triangulate function

class OBJECT_OT_ConvertToCurve(bpy.types.Operator):
    bl_idname = "object.convert_to_mesh"
    bl_label = "Convert to Mesh"

    def execute(self, context):
        self.convert_to_mesh(context)
        return {'FINISHED'}

    def convert_to_mesh(self, context):
        # Placeholder function for converting to curve
        print("Converting to Curve...")
        # Your code to convert to curve goes here

class OBJECT_OT_Triangulate(bpy.types.Operator):
    bl_idname = "object.triangulate"
    bl_label = "Triangulate"

    def execute(self, context):
        self.triangulate_obj(context)
        return {'FINISHED'}

    def triangulate_obj(self, context):
        svg_paste = context.scene.svg_paste

        print(f"Triangulating with method: {svg_paste.triangulation_method}...")

        obj = bpy.context.active_object
        poly = triangulate.obj_to_poly(obj)

        triangulation_method = svg_paste.triangulation_method.lower()

        print(f"Triangulating with method: {triangulation_method} and {svg_paste.triangulation_points} points...")

        bpy.ops.ed.undo_push(message=f"Triangulating with method: {triangulation_method}...")
        points = getattr(triangulate, triangulation_method)(poly, svg_paste.triangulation_points)
        mesh = triangulate.triangulate_poly_and_points(poly, points)
        obj.data = mesh

        
        # print(triangulate.obj_to_shape_01(obj))
        # print(triangulate.obj_to_shape_02(obj))

        # script_file_path = "/home/simone/uv_experiments/foobar.py"; 
        # exec(open(script_file_path).read()) if __import__('os').path.isfile(script_file_path) else print(f"Script file '{script_file_path}' not found.")
        
        # Placeholder function for triangulating
        # Your code to triangulate goes here

class OBJECT_OT_AlignAndResize(bpy.types.Operator):
    bl_idname = "object.align_and_resize"
    bl_label = "Align and Resize"

    def execute(self, context):
        self.align_and_resize(context)
        return {'FINISHED'}

    def align_and_resize(self, context):
        svg_paste = context.scene.svg_paste
        # Placeholder function for aligning and resizing
        print(f"Aligning and resizing target: {svg_paste.target}...")
        # Your code to align and resize goes here

def register():
    bpy.utils.register_class(SVGPasteSettings)
    bpy.types.Scene.svg_paste = bpy.props.PointerProperty(type=SVGPasteSettings)

    bpy.utils.register_class(OBJECT_PT_SVGPastePanel)
    bpy.utils.register_class(OBJECT_OT_PasteSVG)
    bpy.utils.register_class(OBJECT_OT_ConvertToCurve)
    bpy.utils.register_class(OBJECT_OT_Triangulate)
    bpy.utils.register_class(OBJECT_OT_AlignAndResize)

def unregister():
    bpy.utils.unregister_class(SVGPasteSettings)
    del bpy.types.Scene.svg_paste

    bpy.utils.unregister_class(OBJECT_PT_SVGPastePanel)
    bpy.utils.unregister_class(OBJECT_OT_PasteSVG)
    bpy.utils.unregister_class(OBJECT_OT_ConvertToCurve)
    bpy.utils.unregister_class(OBJECT_OT_Triangulate)
    bpy.utils.unregister_class(OBJECT_OT_AlignAndResize)

if __name__ == "__main__":
    register()
