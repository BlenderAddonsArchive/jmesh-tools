import bpy
from bpy.types import Panel

class FC_Shapes_Panel(Panel):
    bl_label = "Shapes"
    bl_idname = "VIEW3D_PT_shapes"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "JMesh"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Shapes:")
        for i, shape in enumerate(scene.shape_list):
            row = layout.row()
            row.prop(shape, "selected", text=f"{shape.name}")
        # layout.operator("shape_tool.draw_shapes", text="Draw Selected Shapes")