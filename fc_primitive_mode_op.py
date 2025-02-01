import bpy
import blf
import bmesh

from bpy.types import Operator
from bpy.props import *

from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils

from .utils.fc_bool_util import select_active, execute_boolean_op, execute_slice_op, is_apply_immediate
from .utils.fc_bevel_util import *
from .utils.fc_view_3d_utils import *

from .types.shape import *
from .types.shape_data import *
from .types.rectangle_shape import *
from .types.polyline_shape import *
from .types.circle_shape import *
from .types.curve_shape import *

from .types.enums import *

from .types.shape_gizmo import *

from .widgets.bl_ui_textbox import *

from .fc_preferences import get_preferences

from . utils.textutils import *

# Primitive mode operator
class FC_Primitive_Mode_Operator(bpy.types.Operator):
    bl_idname = "object.fc_primitve_mode_op"
    bl_label = "Primitive Mode Operator"
    bl_description = "Primitive Mode Operator"
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}

    @classmethod
    def poll(cls, context): 

        if context.window_manager.in_primitive_mode:
            return False

        if context.object == None:
            return True

        return True
		
    def __init__(self):
        self.draw_handle_2d = None
        self.draw_handle_3d = None
        self.draw_event  = None
        self.shapes = []
        self.current_shape = None
        self.add_and_set_current_shape(Polyline_Shape())
                
    def invoke(self, context, event):
        args = (self, context)  

        context.window_manager.in_primitive_mode = True

        self.create_shape(context)    

        self.shape_gizmo = Shape_Gizmo()       

        self.register_handlers(args, context)
                   
        context.window_manager.modal_handler_add(self)

        return {"RUNNING_MODAL"}
    
    def register_handlers(self, args, context):
        self.draw_handle_3d = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback_3d, args, "WINDOW", "POST_VIEW")

        self.draw_handle_2d = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback_2d, args, "WINDOW", "POST_PIXEL")

        self.draw_event = context.window_manager.event_timer_add(0.1, window=context.window)
        
    def unregister_handlers(self, context):

        context.window_manager.in_primitive_mode = False

        context.window_manager.event_timer_remove(self.draw_event)
        bpy.types.SpaceView3D.draw_handler_remove(self.draw_handle_2d, "WINDOW")
        bpy.types.SpaceView3D.draw_handler_remove(self.draw_handle_3d, "WINDOW")
        
        self.draw_handle_2d = None
        self.draw_handle_3d = None
        self.draw_event  = None 

    def add_and_set_current_shape(self, new_shape):
        if self.current_shape != None:
            if self.current_shape.is_created():
                self.shapes.append(new_shape)

        self.current_shape = new_shape

    def get_snapped_mouse_pos(self, mouse_pos_2d, context):

        mouse_pos_3d = self.get_3d_for_mouse(mouse_pos_2d, context)

        if context.scene.use_snapping and mouse_pos_3d is not None:
            mouse_pos_3d = get_snap_3d_vertex(context, mouse_pos_3d)
            mouse_pos_2d = get_2d_vertex(context, mouse_pos_3d)

        return mouse_pos_2d, mouse_pos_3d

    def get_3d_for_mouse(self, mouse_pos_2d, context):

        # Check if to snap to the surface of the object
        if context.scene.snap_to_target:
            mouse_pos_3d = self.current_shape.get_3d_for_2d(mouse_pos_2d, context)

            if mouse_pos_3d is None:
                mouse_pos_3d = get_3d_vertex(context, mouse_pos_2d)
        else:

            mouse_pos_3d = get_3d_vertex(context, mouse_pos_2d)

        return mouse_pos_3d

    def is_mouse_valid(self, mouse_pos_2d):
        return mouse_pos_2d is not None and mouse_pos_2d[0] >= 0 and mouse_pos_2d[1] >= 0

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()

        result = "PASS_THROUGH"

        RM = "RUNNING_MODAL"

        if self.current_shape.shape_action_widgets_handle_event(event):
            return { RM }
                              
        if event.type == "ESC" and event.value == "PRESS":

            was_none = self.current_shape.is_none()

            self.current_shape.reset()

            if was_none:
                self.unregister_handlers(context)
                return { "FINISHED" }

        if event.type == "RET" and event.value == "PRESS":
            self.current_shape.accept()

        # The mouse wheel is moved
        if not self.current_shape.is_none():
            up = event.type == "WHEELUPMOUSE"
            down = event.type == "WHEELDOWNMOUSE"
            if up or down:
                inc = 1 if up else -1
                if self.current_shape.handle_mouse_wheel(inc, context):
                    mouse_pos_2d = (event.mouse_region_x, event.mouse_region_y)
                    mouse_pos_3d = self.get_3d_for_mouse(mouse_pos_2d, context)
                    
                    self.current_shape.create_batch(mouse_pos_3d)
                    result = RM

        # The mouse is moved
        if event.type == "MOUSEMOVE" and not self.current_shape.is_none():
            
            mouse_pos_2d = self.current_shape.get_mouse_pos_2d(event.mouse_region_x, event.mouse_region_y)

            if self.is_mouse_valid(mouse_pos_2d):
                mouse_pos_2d, mouse_pos_3d = self.get_snapped_mouse_pos(mouse_pos_2d, context)

                if self.current_shape.handle_mouse_move(mouse_pos_2d, mouse_pos_3d, event, context):
                    self.current_shape.create_batch(mouse_pos_3d)

        # Left mouse button is released
        if event.value == "RELEASE" and event.type == "LEFTMOUSE":

            mouse_pos_2d = (event.mouse_region_x, event.mouse_region_y)
            self.current_shape.handle_mouse_release(mouse_pos_2d, event, context)

            self.shape_gizmo.mouse_up(context, mouse_pos_2d)

        
        # Left mouse button is pressed
        if event.value == "PRESS" and event.type == "LEFTMOUSE":

            mouse_pos_2d_r = (event.mouse_region_x, event.mouse_region_y)

            if self.is_mouse_valid(mouse_pos_2d_r):

                self.create_shape(context)

                old_bevel_state = False

                # If an object is hit, set it as target
                if event.ctrl:
                    hit, hit_obj = self.current_shape.is_object_hit(mouse_pos_2d_r, context)
                    if hit:
                        context.scene.carver_target = hit_obj

                        # workround: reset bevel modifier to non display to get the right hit face
                        # Seems to be a Blender bug
                        old_bevel_state = set_bevel_display(hit_obj, False)

                mouse_pos_2d, mouse_pos_3d = self.get_snapped_mouse_pos(mouse_pos_2d_r, context)

                # workround: Reset bevel display when it was set
                if old_bevel_state == True:
                   old_bevel_state = set_bevel_display(context.scene.carver_target, True)    

                gizmo_action = self.shape_gizmo.mouse_down(context, event, mouse_pos_2d_r, mouse_pos_3d)
                if gizmo_action:
                    result = RM

                for shape_action in self.current_shape._shape_actions:
                    if shape_action.mouse_inside(context, event, mouse_pos_2d_r, mouse_pos_3d):
                        unitinfo = get_current_units()
                        if type(shape_action) is Shape_Size_Action:
                            if self.current_shape.open_size_action(context, shape_action, unitinfo):
                               result = RM
                        elif type(shape_action) is Shape_Array_Action:
                            if self.current_shape.open_array_input(context, shape_action, unitinfo):
                               result = RM
                        elif type(shape_action) is Shape_CircleArray_Action:
                            if self.current_shape.open_circle_array_input(context, shape_action, unitinfo):
                               result = RM
                        elif type(shape_action) is Shape_Mirror_Action:
                            if self.current_shape.open_mirror_input(context, shape_action, unitinfo):
                               result = RM
                        else:
                            if self.current_shape.open_operation_input(context, shape_action, unitinfo):
                                result = RM                                                      

                if self.current_shape.is_moving() and not self.shape_gizmo.is_dragging():
                    self.current_shape.stop_move(context)

                if self.current_shape.is_sizing():
                    self.current_shape.stop_size(context)

                if self.current_shape.is_extruding():
                    self.current_shape.stop_extrude(context)

                if self.current_shape.is_rotating():
                    self.current_shape.stop_rotate(context)

                if self.current_shape.is_shape_action_active():
                    return { RM }

                if self.current_shape.is_processing():
                    result = RM

                if self.current_shape.is_created() and not gizmo_action and not event.ctrl and not self.current_shape.is_shape_action_active():
                    if self.current_shape.set_vertex_moving(mouse_pos_3d):
                        result = RM

                if not gizmo_action and not self.current_shape.is_shape_action_active():
                    result_mouse_press = self.current_shape.handle_mouse_press(mouse_pos_2d, mouse_pos_3d, event, context)
                    if  result_mouse_press == 2:

                        self.create_object(context)

                    else:
                        # So that the direction is defined during shape
                        # creation, not when it is extruded
                        if self.current_shape.is_processing():
                            view_context = ViewContext(context)
                            self.current_shape.set_view_context(view_context)

                        elif self.current_shape.is_created() and result_mouse_press == 1:
                            self.add_new_shape()
                    
                self.current_shape.create_batch(mouse_pos_3d)

        # Keyboard
        if event.value == "PRESS":

            if event.type == "M" and event.alt:
                if self.current_shape.can_convert_to_mesh():
                    self.create_mesh(context, False)
                    result = RM
                elif self.current_shape.can_create_from_mesh():
                    self.current_shape = Polyline_Shape()
                    context.scene.primitive_type == "Polyline"
                    self.current_shape.create_from_mesh(context)
                    result = RM

            if event.type == "S":
                mouse_pos_2d = (event.mouse_region_x, event.mouse_region_y)
                mouse_pos_2d, mouse_pos_3d = self.get_snapped_mouse_pos(mouse_pos_2d, context)

                if self.current_shape.start_size(mouse_pos_3d):

                    # TODO: Also size the extrusion?
                    self.current_shape.reset_extrude()
                    result = RM

            # try to move the shape
            if event.type == "G":
                mouse_pos_2d = (event.mouse_region_x, event.mouse_region_y)

                mouse_pos_2d, mouse_pos_3d = self.get_snapped_mouse_pos(mouse_pos_2d, context)

                if self.current_shape.start_move(mouse_pos_3d):
                    result = RM

            if self.current_shape.is_moving():
                if event.type in ["X", "Y", "N"]:
                    self.current_shape.set_move_axis(event.type)
                    result = RM

            # try to rotate the shape
            if event.type == "R":
                mouse_pos_2d = (event.mouse_region_x, event.mouse_region_y)

                mouse_pos_3d = self.get_3d_for_mouse(mouse_pos_2d, context)

                if self.current_shape.start_rotate(mouse_pos_2d, mouse_pos_3d, context):
                    self.current_shape.create_batch()
                    result = RM

            # Try set mirror type for primitives
            if event.type == "M" and not event.alt:
                if self.current_shape.is_none():
                    self.current_shape.set_next_mirror(context)
                    self.current_shape.build_actions()
                    result = RM

            # try to extrude the shape
            if self.current_shape.is_extruding():
                if (event.type == "DOWN_ARROW" or event.type == "UP_ARROW"):
                    self.current_shape.handle_extrude(event.type == "UP_ARROW", context)
                    self.current_shape.create_batch()
                    result = RM
                elif (event.type in ["X", "Y", "Z", "N"]):
                    self.current_shape.set_extrude_axis(event.type)
                    self.current_shape.create_batch()
                    result = RM

            if event.type == "E":
                mouse_pos_2d = (event.mouse_region_x, event.mouse_region_y)
                mouse_pos_3d = self.get_3d_for_mouse(mouse_pos_2d, context)

                if self.current_shape.start_extrude(mouse_pos_2d, mouse_pos_3d, context):
                    self.current_shape.create_batch()
                    result = RM

            # toggle input method
            if event.type == "I":
                self.current_shape.set_next_input_method(context)
                self.current_shape.build_actions()

                result = RM

            # toggle bool mode
            if event.type == "O":
                context.scene.bool_mode = next_enum(context.scene.bool_mode, 
                                                    context.scene, "bool_mode")

                self.current_shape.build_actions()

                result = RM

            if event.type == "C":
                if self.current_shape.can_set_center_type():
                    context.scene.center_type = next_enum(context.scene.center_type, context.scene, "center_type")
                    self.current_shape.build_actions()
                    result = RM

            if event.type == "F":
                if self.current_shape.can_start_from_center():
                    context.scene.start_center = not context.scene.start_center
                    self.current_shape.build_actions()
                    result = RM
                           
            # toggle primitve  
            if event.type == "P":
                if self.current_shape.is_none():
                    context.scene.primitive_type = next_enum(context.scene.primitive_type, 
                                                        context.scene, "primitive_type")

                    self.create_shape(context)
                    result = RM
             
        return { result }

    def add_new_shape(self):
        pass
        # scene = bpy.context.scene
        # new_shape = scene.shape_list.add()
        # new_shape.name = "Shape 1"
        # new_shape.shape_type = ShapeType.POLYGON

    def create_shape(self, context):
        if self.current_shape.is_none():
            if context.scene.primitive_type == "Circle":
                self.current_shape = Circle_Shape()
            elif context.scene.primitive_type == "Polyline":
                self.current_shape = Polyline_Shape()
            elif context.scene.primitive_type == "Curve":
                self.current_shape = Curve_Shape()
            else:
                self.current_shape = Rectangle_Shape()

            self.current_shape.initialize(context)

    def create_object(self, context):
        # TODO: Refactor -> Creation factory with shape as parameter
        if self.current_shape.connected_shape():
            self.create_mesh(context, True)
        else:
            self.create_curve(context)

    def create_curve(self, context):
        curve_shape = self.current_shape
        if curve_shape.is_2_points_input():
            self.create_bezier(context)
        else:
            self.create_path(context)

    def set_bevel(self, curve):
        obj_data = curve.data
        obj_data.bevel_depth = 0.05
        obj_data.resolution_u = 24
        obj_data.bevel_resolution = 12
        obj_data.fill_mode = 'FULL'  


    def create_path(self, context):
        if context.object is not None:
            bpy.ops.object.mode_set(mode='OBJECT')

        curve_shape = self.current_shape
        bpy.ops.curve.primitive_nurbs_path_add(enter_editmode=True)

        self.set_bevel(context.active_object)

        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.delete()

        for point in curve_shape.get_points():
            bpy.ops.curve.vertex_add(location=point)

        self.current_shape.reset()


    def create_bezier(self, context):
        if context.object is not None:
            bpy.ops.object.mode_set(mode='OBJECT')

        curve_shape = self.current_shape
        bpy.ops.curve.primitive_bezier_curve_add(enter_editmode=True, location=(0, 0, 0))

        curve = context.active_object
        
        self.set_bevel(curve)

        bez_points = curve.data.splines[0].bezier_points
        point_count = len(bez_points) - 1

        norm_start = curve_shape.get_normal_start()
        norm_end = curve_shape.get_normal_end()

        bez_points[0].co = curve_shape.get_start_point()
        if norm_start is not None:
            bez_points[0].handle_right = bez_points[0].co + norm_start
            bez_points[0].handle_left = bez_points[0].co - norm_start

        bez_points[point_count].co = curve_shape.get_end_point()
        if norm_end is not None:
            bez_points[point_count].handle_right = bez_points[point_count].co - norm_end
            bez_points[point_count].handle_left = bez_points[point_count].co + norm_end

        self.current_shape.reset()

    def add_bool_obj_to_collection(self, context, obj):

        # Ensure collection exists
        coll_name = "JM Bool Pending"
        if coll_name not in bpy.data.collections:
            new_collection = bpy.data.collections.new(coll_name)
            context.scene.collection.children.link(new_collection)
        else:
            new_collection = bpy.data.collections[coll_name]

        new_collection.objects.link(obj)

    def create_mesh(self, context, extrude_mesh):
        current_mode = None
        try:
            if context.object is not None:
                current_mode = context.object.mode
                bpy.ops.object.mode_set(mode='OBJECT')

            is_bool_create = (context.scene.bool_mode == "Create" or not extrude_mesh)

            # Create a mesh and an object and 
            # add the object to the scene collection
            mesh = bpy.data.meshes.new(str(self.current_shape) + "_Mesh")
            obj  = bpy.data.objects.new(str(self.current_shape) + "_Object", mesh)

            if is_apply_immediate() or is_bool_create:
                bpy.context.scene.collection.objects.link(obj)
            else:
                self.add_bool_obj_to_collection(context, obj)
            
            bpy.ops.object.select_all(action='DESELECT')

            bpy.context.view_layer.objects.active = obj
            obj.select_set(state=True)

            # Create a bmesh and add the vertices
            # added by mouse clicks
            bm = bmesh.new()
            bm.from_mesh(mesh) 

            for v in self.current_shape.vertices:
                bm.verts.new(v)
            
            bm.verts.index_update()
            bm.faces.new(bm.verts)

            if self.current_shape.has_mirror:
                # Add faces for the mirrored vertices
                mirror_verts = []
                for v in self.current_shape.vertices_mirror:
                    mirror_verts.append(bm.verts.new(v))
                
                bm.verts.index_update()
                bm.faces.new(mirror_verts)

            for vc in self.current_shape.vertex_containers:

                # Add faces for vertex containers like arrays
                ctr_verts = []
                for v in vc.vertices:
                    ctr_verts.append(bm.verts.new(v))
                
                bm.verts.index_update()
                bm.faces.new(ctr_verts)

            # Extrude mesh if extrude mesh option is enabled
            if extrude_mesh:
                self.extrude_mesh(context, bm, is_bool_create)

            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

            bm.to_mesh(mesh)
            bm.free()

            bpy.context.view_layer.objects.active = obj
            obj.select_set(state=True)

            self.remove_doubles()

            # set origin to geometry
            bpy.ops.object.editmode_toggle()
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')

            if not extrude_mesh:
                bpy.ops.object.editmode_toggle()
                bpy.ops.mesh.select_all(action='SELECT')

            # Fast bool modes
            if not is_bool_create:

                target_obj = bpy.context.scene.carver_target
                if target_obj is not None:

                    bool_mode_id = self.get_bool_mode_id(context.scene.bool_mode)
                    if bool_mode_id != 3:
                        execute_boolean_op(context, target_obj, bool_mode_id)
                    else:
                        execute_slice_op(context, target_obj)

                    # delete the bool object if apply immediate is checked
                    # Apply not needed anymore here?
                    #if is_apply_immediate():
                        # bpy.ops.object.delete()
                    #else:
                    #    obj.hide_set(True)

                    select_active(target_obj)
        except:
            pass
        finally:
            if extrude_mesh and (current_mode is not None):
                bpy.ops.object.mode_set(mode=current_mode)


    def get_bool_mode_id(self, bool_name):
        if bool_name == "Difference":
            return 0
        elif bool_name == "Union":
            return 1
        elif bool_name == "Intersect":
            return 2
        elif bool_name == "Slice":
            return 3
        return -1

    def remove_doubles(self):
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles()       

    def extrude_mesh(self, context, bm, is_bool_create):
        length = 1
        if not is_bool_create:
            length = 100
        
        dir = self.current_shape.get_dir() * length

        if self.current_shape.is_extruded():
            dir = self.current_shape.get_dir() * self.current_shape.extrusion

        # extr_geom = bm.edges[:]
        extr_geom = bm.faces[:]

        r = bmesh.ops.extrude_face_region(bm, geom=extr_geom)
        verts = [e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=dir, verts=verts)

    def finish(self):
        self.unregister_handlers(bpy.context)
        return {"FINISHED"}

    def draw_action_line(self, action, pos_y, pos_x):

        prefs = get_preferences()
        lc = prefs.osd_label_color
        size = prefs.osd_font_size
        off_x = prefs.osd_offset_x

        blf.color(1, lc[0], lc[1], lc[2], lc[3])
        blf.position(1, off_x, pos_y , 1)

        title = action.title
        if action.content != "":
            title += ":"

        blf.draw(1, title) 
     
        if(action.content != ""):
            blf.position(1, pos_x[0], pos_y , 1)
            blf.draw(1, action.content) 

        tc = prefs.osd_text_color
        blf.color(1, tc[0], tc[1], tc[2], tc[3])
        blf.position(1, pos_x[1], pos_y, 1)
        blf.draw(1, action.id)

	# Draw handler to paint in pixels
    def draw_callback_2d(self, op, context):

        self.current_shape.draw_text()

        self.shape_gizmo.draw(self.current_shape)

        self.current_shape.shape_actions_draw()

        self.current_shape.shape_action_widgets_draw()

        # Draw text for primitive mode
        fsize = get_preferences().osd_font_size
        off_x = get_preferences().osd_offset_x
        blf_set_size(1, fsize)

        line_height = 18
        pos_x = [115, 200]
        pos_y = 150

        if fsize >= 20:
            line_height = 23
            pos_x = [200, 380]
            pos_y = 200
        elif fsize >= 17:
            line_height = 22
            pos_x = [160, 285]
            pos_y = 190
        elif fsize >= 14:
            pos_x = [155, 270]
            pos_y = 160

        pos_x[0] += off_x
        pos_x[1] += off_x

        self.draw_action_line(self.current_shape.actions[0], pos_y, pos_x)

        for index in range(len(self.current_shape.actions)-1):
            action = self.current_shape.actions[index+1]
            self.draw_action_line(action, (pos_y - 10) - (index + 1) * line_height, pos_x)

        blf.color(1, 1, 1, 1, 1)

    def get_actions_height(self, size):
        return len(self.current_shape.actions) * size


	# Draw handler to paint onto the screen
    def draw_callback_3d(self, op, context):
        
        self.current_shape.draw(context)

        self.current_shape.set_shape_actions_position()