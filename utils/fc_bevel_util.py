import bpy
from bpy.props import *

def try_find_bevel_op(bevel_objects):
    for bevel_obj in bevel_objects:
        bevel_mod = bevel_obj.modifiers.get("Bevel")
        if(bevel_mod is not None):
            return bevel_mod
    return None

def has_bevel_mod(obj):
    bevel_mod = obj.modifiers.get("Bevel")
    return bevel_mod is not None

# Sets the bevel viewport display and returns the old state
def set_bevel_display(obj, enabled):
    if not has_bevel_mod(obj):
        return False

    bevel_mod = obj.modifiers.get("Bevel")
    result = bevel_mod.show_viewport
    bevel_mod.show_viewport = enabled

    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()

    return result


def apply_sharp_edges():

    # Set smooth shading for the target object
    bpy.ops.object.shade_smooth()

    # switch to edit mode and select sharp edges
    bpy.ops.object.editmode_toggle()
    
    bpy.context.tool_settings.mesh_select_mode = (False, True, False)

    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.edges_select_sharp()
    
    # Mark edges as sharp
    bpy.ops.mesh.mark_sharp()
    bpy.ops.transform.edge_bevelweight(value=1)

    # Back to object mode
    bpy.ops.object.editmode_toggle()

def execute_bevel(bevel_objects):
    if len(bevel_objects) == 0:
        return

    # Default value for bevel
    width = 0.007

    bevel_op = try_find_bevel_op(bevel_objects)
    if(bevel_op is not None):
        width = bevel_op.width

    for target_obj in bevel_objects:

        bpy.context.view_layer.objects.active = target_obj
        
        # Apply the scale before beveling
        bpy.ops.object.transform_apply(scale=True, location=False, rotation=False)
               
        # Set the data to autosmooth
        mesh = bpy.context.object.data
        if bpy.app.version < (4, 2, 0):
            mesh.use_auto_smooth = True  # or other logic for older versions
            bpy.context.object.data.auto_smooth_angle = 1.0472
        
        # Remove the bevel modifier if exists
        modifier_to_remove = target_obj.modifiers.get("Bevel")
        if(modifier_to_remove is not None):
            target_obj.modifiers.remove(modifier_to_remove)

        # Remove the Weighted Normal modifier if exists
        modifier_to_remove = target_obj.modifiers.get("WeightedNormal")
        if(modifier_to_remove is not None):
            target_obj.modifiers.remove(modifier_to_remove)
            
        # Add a new bevel modifier
        bpy.ops.object.modifier_add(type = 'BEVEL')

        # get the last added modifier
        bevel = target_obj.modifiers[-1]
        bevel.limit_method = 'ANGLE'
        bevel.use_clamp_overlap = False
        bevel.width = width
        bevel.miter_outer = 'MITER_ARC'
        bevel.segments = 3
        bevel.profile = 0.7

        # add a weighted normal modifier after the bevel
        bpy.ops.object.modifier_add(type='WEIGHTED_NORMAL')
        weighted_mod = target_obj.modifiers[-1]
        weighted_mod.keep_sharp = True
        
        bpy.ops.object.shade_smooth()
        # apply_sharp_edges()
